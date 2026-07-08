# Examples

## 1. CSV shop demo (2 minutes)

```bash
cd examples/shop
python make_data.py            # writes data/customers.csv + data/orders.csv
adp init --name shop-demo
adp connect --name shop --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 10000 --output parquet
adp quality-check --report quality.md
adp semantic-model --format cube --out model/cubes.yml
adp docs
adp ui                          # browse it all at http://127.0.0.1:8765
```

## 2. SDK usage

```python
from ai_data_platform import ADPClient

client = ADPClient("examples/shop")
client.scan()
client.profile()
result = client.generate_data(rows=50_000, output_format="duckdb")
print(client.quality_check()["quality_score"])
```

## 3. MCP from Claude Code

```bash
claude mcp add adp -- adp mcp-server --project "$(pwd)/examples/shop"
# then in Claude: "scan my sources, profile them, and generate 10k rows of test data"
```

## 4. Cube.js semantic layer

```bash
adp semantic-model --format cube --out model/cubes.yml
docker compose --profile semantic up cube    # dev playground on :4000
```
