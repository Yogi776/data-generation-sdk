package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/ai-data-platform/adp-executor/internal/exec"
	"github.com/ai-data-platform/adp-executor/internal/plan"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "run":
		run(os.Args[2:])
	default:
		usage()
		os.Exit(2)
	}
}

func run(args []string) {
	fs := flag.NewFlagSet("run", flag.ExitOnError)
	planPath := fs.String("plan", "", "Path to Plan IR JSON")
	outputDir := fs.String("output", "output", "Output directory")
	format := fs.String("format", "parquet", "Output format: parquet|csv")
	_ = fs.Parse(args)

	if *planPath == "" {
		fmt.Fprintln(os.Stderr, "--plan is required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*planPath)
	if err != nil {
		emitErr(err)
		return
	}
	var p plan.GenerationPlan
	if err := json.Unmarshal(raw, &p); err != nil {
		emitErr(err)
		return
	}
	result, err := exec.Run(p, *outputDir, *format)
	if err != nil {
		emitErr(err)
		return
	}
	emitOK(result)
}

func emitOK(result map[string]any) {
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": true, "result": result})
}

func emitErr(err error) {
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": false, "error": err.Error()})
	os.Exit(1)
}

func usage() {
	fmt.Fprintf(os.Stderr, "adp-executor — Plan IR generation worker\n\n")
	fmt.Fprintf(os.Stderr, "Usage:\n  adp-executor run --plan plan.json --output output/ [--format parquet]\n")
}
