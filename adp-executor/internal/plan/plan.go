package plan

// GenerationPlan mirrors Python Plan IR v1 (generator/engine.py).

type GenerationPlan struct {
	PlanIRVersion int         `json:"plan_ir_version"`
	Seed          int         `json:"seed"`
	ChunkRows     int         `json:"chunk_rows"`
	Tables        []TablePlan `json:"tables"`
}

type TablePlan struct {
	Name        string           `json:"name"`
	Rows        int              `json:"rows"`
	Columns     []ColumnPlan     `json:"columns"`
	ForeignKeys []ForeignKeyPlan `json:"foreign_keys"`
}

type ColumnPlan struct {
	Name      string         `json:"name"`
	Sampler   string         `json:"sampler"`
	Params    map[string]any `json:"params"`
	NullRatio float64        `json:"null_ratio"`
	Derive    map[string]any `json:"derive"`
}

type ForeignKeyPlan struct {
	Column       string `json:"column"`
	ParentTable  string `json:"parent_table"`
	ParentColumn string `json:"parent_column"`
	Relationship string `json:"relationship"`
}
