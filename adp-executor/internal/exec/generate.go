package exec

import (
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"math"
	"math/rand/v2"
	"os"
	"path/filepath"

	"github.com/ai-data-platform/adp-executor/internal/plan"
	"github.com/google/uuid"
)

type keyPool map[string]map[string][]any

func tableRNG(seed int, table string, chunk int) *rand.Rand {
	h := sha256.Sum256([]byte(fmt.Sprintf("%d:%s:%d", seed, table, chunk)))
	seed64 := binary.BigEndian.Uint64(h[:8])
	return rand.New(rand.NewPCG(seed64, seed64^0x9e3779b97f4a7c15))
}

func Run(p plan.GenerationPlan, outputDir, format string) (map[string]any, error) {
	if format != "parquet" && format != "csv" {
		return nil, fmt.Errorf("go executor supports parquet/csv only (got %q)", format)
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return nil, err
	}
	pool := make(keyPool)
	results := make(map[string]any)
	for _, tp := range p.Tables {
		path, keys, err := generateTable(p, tp, outputDir, format, pool)
		if err != nil {
			return nil, err
		}
		for col, vals := range keys {
			if pool[tp.Name] == nil {
				pool[tp.Name] = make(map[string][]any)
			}
			pool[tp.Name][col] = vals
		}
		results[tp.Name] = map[string]any{"rows": tp.Rows, "path": path}
	}
	return results, nil
}

func generateTable(
	p plan.GenerationPlan,
	tp plan.TablePlan,
	outputDir, format string,
	pool keyPool,
) (string, map[string][]any, error) {
	colNames := make([]string, 0, len(tp.Columns)+len(tp.ForeignKeys))
	for _, c := range tp.Columns {
		colNames = append(colNames, c.Name)
	}
	for _, fk := range tp.ForeignKeys {
		colNames = append(colNames, fk.Column)
	}

	chunkRows := p.ChunkRows
	if chunkRows <= 0 {
		chunkRows = 100_000
	}
	cols := make(map[string][]any)
	keyCols := make(map[string][]any)

	for chunkIdx, offset := 0, 0; offset < tp.Rows || (offset == 0 && tp.Rows == 0); chunkIdx++ {
		n := chunkRows
		if offset+n > tp.Rows {
			n = tp.Rows - offset
		}
		rng := tableRNG(p.Seed, tp.Name, chunkIdx)

		for _, cp := range tp.Columns {
			series, err := sampleColumn(cp, n, offset, rng)
			if err != nil {
				return "", nil, err
			}
			cols[cp.Name] = append(cols[cp.Name], series...)
			if cp.Sampler == "sequence" || cp.Sampler == "uuid" {
				keyCols[cp.Name] = append(keyCols[cp.Name], series...)
			}
		}
		for _, fk := range tp.ForeignKeys {
			parent := pool[fk.ParentTable][fk.ParentColumn]
			if len(parent) == 0 {
				return "", nil, fmt.Errorf("no parent keys for %s.%s", tp.Name, fk.Column)
			}
			out := make([]any, n)
			for i := 0; i < n; i++ {
				out[i] = parent[rng.IntN(len(parent))]
			}
			cols[fk.Column] = append(cols[fk.Column], out...)
		}

		offset += n
		if n == 0 || offset >= tp.Rows {
			break
		}
	}

	path, err := writeCSV(outputDir, tp.Name, colNames, cols)
	if format == "parquet" {
		// v0: parquet via DuckDB-less stub — write csv then note path; full parquet in v1.
		// For now duplicate as .parquet extension is not valid; callers should use csv or Python.
		return path, keyCols, fmt.Errorf("parquet output not yet implemented in Go executor v0; use csv or Python executor")
	}
	return path, keyCols, err
}

func sampleColumn(cp plan.ColumnPlan, n, offset int, rng *rand.Rand) ([]any, error) {
	out := make([]any, n)
	switch cp.Sampler {
	case "sequence":
		start := 1
		if v, ok := cp.Params["start"].(float64); ok {
			start = int(v)
		}
		for i := 0; i < n; i++ {
			out[i] = int64(start + offset + i)
		}
	case "uuid":
		for i := 0; i < n; i++ {
			out[i] = uuid.New().String()
		}
	case "choice":
		valsRaw, ok := cp.Params["values"].([]any)
		if !ok {
			return nil, fmt.Errorf("choice sampler missing values")
		}
		vals := make([]any, len(valsRaw))
		weights := make([]float64, len(valsRaw))
		for i, item := range valsRaw {
			m, ok := item.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("invalid choice item")
			}
			vals[i] = m["value"]
			if w, ok := m["weight"].(float64); ok {
				weights[i] = w
			}
		}
		total := 0.0
		for _, w := range weights {
			total += w
		}
		if total <= 0 {
			total = 1
		}
		for i := 0; i < n; i++ {
			r := rng.Float64() * total
			acc := 0.0
			for j, w := range weights {
				acc += w
				if r <= acc {
					out[i] = vals[j]
					break
				}
			}
		}
	case "normal":
		mean, std := 0.0, 1.0
		if v, ok := cp.Params["mean"].(float64); ok {
			mean = v
		}
		if v, ok := cp.Params["std"].(float64); ok {
			std = v
		}
		for i := 0; i < n; i++ {
			out[i] = mean + std*rng.NormFloat64()
		}
	case "uniform_int":
		lo, hi := 0.0, 100.0
		if v, ok := cp.Params["min"].(float64); ok {
			lo = v
		}
		if v, ok := cp.Params["max"].(float64); ok {
			hi = v
		}
		span := int(hi-lo) + 1
		if span < 1 {
			span = 1
		}
		for i := 0; i < n; i++ {
			out[i] = int64(lo) + int64(rng.IntN(span))
		}
	case "words":
		words := []string{"lorem", "ipsum", "data", "sample", "value"}
		for i := 0; i < n; i++ {
			out[i] = words[rng.IntN(len(words))]
		}
	default:
		for i := 0; i < n; i++ {
			out[i] = nil
		}
	}
	if cp.NullRatio > 0 {
		for i := 0; i < n; i++ {
			if rng.Float64() < cp.NullRatio {
				out[i] = nil
			}
		}
	}
	return out, nil
}

func writeCSV(dir, table string, colNames []string, cols map[string][]any) (string, error) {
	path := filepath.Join(dir, table+".csv")
	f, err := os.Create(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	n := 0
	if len(colNames) > 0 {
		n = len(cols[colNames[0]])
	}
	for i, c := range colNames {
		if i > 0 {
			_, _ = f.WriteString(",")
		}
		_, _ = f.WriteString(c)
	}
	_, _ = f.WriteString("\n")
	for i := 0; i < n; i++ {
		for j, c := range colNames {
			if j > 0 {
				_, _ = f.WriteString(",")
			}
			v := cols[c][i]
			if v == nil {
				continue
			}
			switch t := v.(type) {
			case string:
				_, _ = f.WriteString(t)
			case int64:
				_, _ = f.WriteString(fmt.Sprintf("%d", t))
			case float64:
				if math.IsNaN(t) || math.IsInf(t, 0) {
					continue
				}
				_, _ = f.WriteString(fmt.Sprintf("%g", t))
			default:
				_, _ = f.WriteString(fmt.Sprint(v))
			}
		}
		_, _ = f.WriteString("\n")
	}
	return path, nil
}
