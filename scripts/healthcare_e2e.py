"""Healthcare-claims end-to-end: generate + quality check + Patient 360 SQL."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ai_data_platform.mcp.server import create_server


def parse_result(result) -> dict:
    if isinstance(result, tuple):
        content_list = result[0]
        if isinstance(content_list, list) and hasattr(content_list[0], "text"):
            return json.loads(content_list[0].text)
    if isinstance(result, list):
        return json.loads(result[0].text)
    if hasattr(result, "text"):
        return json.loads(result.text)
    return json.loads(str(result))


async def run():
    project = "/Users/yogeshkhangode/experiment-personal/Data Generator/healthcare-claims"
    spec_path = "/Users/yogeshkhangode/experiment-personal/Data Generator/healthcare-claims/spec.yaml"
    spec_yaml = Path(spec_path).read_text(encoding="utf-8")
    server = create_server(project)

    # ── Step 1: Apply spec + Generate ──────────────────────────────────
    print("=" * 60)
    print("STEP 1 — APPLY SPEC + GENERATE 5,000 rows")
    print("=" * 60)
    result = await server.call_tool(
        "apply_spec",
        {"spec_yaml": spec_yaml}
    )
    r = parse_result(result)
    print(f"apply_spec ok: {r.get('ok')}")
    if not r.get("ok"):
        print(f"ERROR: {r.get('error', r)}")
        return

    result = await server.call_tool(
        "generate_synthetic_data",
        {"rows": 5000, "seed": 99, "output_format": "parquet"},
    )
    r = parse_result(result)
    print(f"generate ok: {r.get('ok')}")
    if r.get("ok"):
        for table, info in r["result"]["tables"].items():
            print(f"  {table}: {info['rows']:,} rows")
    else:
        print(f"ERROR: {r.get('error', r)}")

    # ── Step 1b: Register datasets so SQL explorer works ───────────────
    print("\n" + "=" * 60)
    print("STEP 1b — REGISTER DATASETS")
    print("=" * 60)
    result = await server.call_tool(
        "register_datasets",
        {
            "data_dir": "/Users/yogeshkhangode/experiment-personal/Data Generator/healthcare-claims/output"
        },
    )
    r = parse_result(result)
    print(f"register_datasets ok: {r.get('ok')}")
    if not r.get("ok"):
        print(f"  hint: {r.get('error', '')[:200]}")
        # Fallback: try list_datasets to confirm explorer state
        result2 = await server.call_tool("list_datasets", {})
        r2 = parse_result(result2)
        print(f"  list_datasets: {r2.get('result', {})}")

    # ── Step 2: Quality check ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2 — QUALITY CHECK")
    print("=" * 60)
    result = await server.call_tool("run_quality_check", {})
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        print(f"  quality_score: {r['result']['quality_score']}")
        for cat, score in r["result"].get("category_scores", {}).items():
            print(f"  {cat}: {score}")
        failing = r["result"].get("failing_checks", [])
        print(f"  failing_checks: {len(failing)}")
        for fc in failing[:10]:
            print(f"    {fc['table']}.{fc['column']}: {fc['rule']} — {fc['evidence']}")

    # ── Step 3: Patient 360 queries ────────────────────────────────────
    queries = [
        (
            "Patient demographics summary",
            """
            SELECT
                COUNT(DISTINCT patient_id) AS total_patients,
                COUNT(DISTINCT CASE WHEN account_status = 'Active' THEN patient_id END) AS active_patients,
                ROUND(AVG(age), 1) AS avg_age,
                gender,
                COUNT(*) AS cnt,
                ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(), 1) AS pct
            FROM dim_patient
            GROUP BY gender ORDER BY cnt DESC
            """,
        ),
        (
            "Patient risk stratification",
            """
            SELECT
                CASE
                    WHEN risk_score >= 70 THEN 'High Risk'
                    WHEN risk_score >= 40 THEN 'Medium Risk'
                    ELSE 'Low Risk'
                END AS risk_tier,
                COUNT(*) AS patients,
                ROUND(AVG(chronic_conditions_count), 1) AS avg_chronic_conditions,
                ROUND(AVG(annual_income), 0) AS avg_income,
                ROUND(100.0*SUM(CASE WHEN smoking_status = 'Current' THEN 1 ELSE 0 END)/COUNT(*),1) AS smoking_pct
            FROM dim_patient
            WHERE risk_score IS NOT NULL
            GROUP BY 1 ORDER BY patients DESC
            """,
        ),
        (
            "Top 10 diagnoses by patient count",
            """
            SELECT
                d.diagnosis_description,
                d.diagnosis_category,
                d.severity,
                COUNT(DISTINCT e.patient_id) AS patients,
                COUNT(e.encounter_id) AS encounters,
                ROUND(AVG(e.length_of_stay), 1) AS avg_los,
                ROUND(SUM(e.total_charges), 0) AS total_charges
            FROM fact_encounter e
            JOIN dim_diagnosis d ON e.primary_diagnosis_id = d.diagnosis_id
            GROUP BY 1,2,3
            ORDER BY patients DESC LIMIT 10
            """,
        ),
        (
            "Encounters by type and department",
            """
            SELECT
                e.encounter_type,
                e.department,
                COUNT(*) AS encounters,
                ROUND(AVG(e.length_of_stay), 1) AS avg_los,
                ROUND(SUM(e.total_charges)/COUNT(*), 0) AS avg_charges_per_encounter,
                ROUND(100.0*SUM(CASE WHEN e.readmission_30day = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS readmission_rate_pct,
                ROUND(100.0*SUM(CASE WHEN e.complication_flag = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS complication_rate_pct
            FROM fact_encounter e
            GROUP BY 1,2 ORDER BY encounters DESC LIMIT 12
            """,
        ),
        (
            "Claims adjudication summary",
            """
            SELECT
                c.status,
                COUNT(*) AS claims,
                ROUND(SUM(c.billed_amount), 0) AS total_billed,
                ROUND(SUM(c.allowed_amount), 0) AS total_allowed,
                ROUND(SUM(c.paid_amount), 0) AS total_paid,
                ROUND(SUM(c.patient_responsibility), 0) AS total_patient_resp,
                ROUND(100.0*SUM(CASE WHEN c.denial_flag = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS denial_rate_pct,
                ROUND(AVG(c.days_to_adjudicate), 1) AS avg_days_to_adjudicate
            FROM fact_claim c
            GROUP BY 1 ORDER BY claims DESC
            """,
        ),
        (
            "Provider performance (top 10 by encounters)",
            """
            SELECT
                p.provider_name,
                p.specialty,
                p.city,
                COUNT(e.encounter_id) AS encounters,
                COUNT(DISTINCT e.patient_id) AS unique_patients,
                ROUND(AVG(e.length_of_stay), 1) AS avg_los,
                ROUND(SUM(e.total_charges)/COUNT(*), 0) AS avg_charges,
                ROUND(100.0*SUM(CASE WHEN e.discharge_status = 'Expired' THEN 1 ELSE 0 END)/COUNT(*),1) AS mortality_rate_pct,
                ROUND(p.average_rating, 2) AS provider_rating
            FROM fact_encounter e
            JOIN dim_provider p ON e.provider_id = p.provider_id
            GROUP BY 1,2,3,9
            ORDER BY encounters DESC LIMIT 10
            """,
        ),
        (
            "Payer mix and claim costs",
            """
            SELECT
                pay.payer_name,
                pay.payer_type,
                COUNT(DISTINCT c.patient_id) AS patients,
                COUNT(c.claim_id) AS claims,
                ROUND(SUM(c.billed_amount), 0) AS total_billed,
                ROUND(SUM(c.paid_amount), 0) AS total_paid,
                ROUND(SUM(c.paid_amount)*100.0/SUM(c.billed_amount), 1) AS paid_to_billed_ratio_pct,
                ROUND(AVG(c.days_to_adjudicate), 1) AS avg_days,
                ROUND(100.0*SUM(CASE WHEN c.denial_flag = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS denial_rate_pct
            FROM fact_claim c
            JOIN dim_payer pay ON c.payer_id = pay.payer_id
            GROUP BY 1,2 ORDER BY claims DESC LIMIT 10
            """,
        ),
        (
            "Lab result abnormality summary",
            """
            SELECT
                test_category,
                test_name,
                COUNT(*) AS tests,
                COUNT(DISTINCT patient_id) AS patients,
                ROUND(100.0*SUM(CASE WHEN is_abnormal = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS abnormal_rate_pct,
                ROUND(100.0*SUM(CASE WHEN critical_flag = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS critical_rate_pct,
                ROUND(AVG(turnaround_hours), 1) AS avg_turnaround_hours
            FROM fact_lab_result
            GROUP BY 1,2 ORDER BY tests DESC LIMIT 10
            """,
        ),
        (
            "Chronic disease prevalence by age group",
            """
            SELECT
                CASE
                    WHEN age < 18 THEN 'Pediatric (0-17)'
                    WHEN age < 35 THEN 'Young Adult (18-34)'
                    WHEN age < 50 THEN 'Middle Age (35-49)'
                    WHEN age < 65 THEN 'Older Adult (50-64)'
                    ELSE 'Senior (65+)'
                END AS age_group,
                COUNT(*) AS patients,
                ROUND(AVG(chronic_conditions_count), 1) AS avg_chronic,
                ROUND(100.0*SUM(CASE WHEN smoking_status = 'Current' THEN 1 ELSE 0 END)/COUNT(*),1) AS smoking_pct,
                ROUND(AVG(risk_score), 1) AS avg_risk_score,
                ROUND(AVG(annual_income), 0) AS avg_income
            FROM dim_patient
            GROUP BY 1 ORDER BY avg_chronic DESC
            """,
        ),
        (
            "Insurance coverage mix",
            """
            SELECT
                insurance_type,
                coverage_type,
                COUNT(*) AS patients,
                ROUND(AVG(annual_income), 0) AS avg_income,
                ROUND(100.0*SUM(CASE WHEN account_status = 'Active' THEN 1 ELSE 0 END)/COUNT(*),1) AS active_rate_pct
            FROM dim_patient
            GROUP BY 1,2 ORDER BY patients DESC LIMIT 10
            """,
        ),
        (
            "Geographic patient distribution",
            """
            SELECT
                country,
                state,
                city,
                COUNT(*) AS patients,
                ROUND(AVG(age), 1) AS avg_age,
                COUNT(DISTINCT primary_provider_id) AS providers_seen,
                COUNT(DISTINCT primary_diagnosis_id) AS unique_diagnoses
            FROM dim_patient
            GROUP BY 1,2,3 ORDER BY patients DESC LIMIT 15
            """,
        ),
        (
            "Encounter trends by month",
            """
            SELECT
                DATE_TRUNC('month', encounter_date) AS month,
                COUNT(*) AS encounters,
                COUNT(DISTINCT patient_id) AS unique_patients,
                ROUND(AVG(length_of_stay), 1) AS avg_los,
                ROUND(SUM(total_charges), 0) AS total_charges,
                ROUND(SUM(total_charges)/COUNT(*), 0) AS avg_charges,
                ROUND(100.0*SUM(CASE WHEN encounter_type = 'Emergency' THEN 1 ELSE 0 END)/COUNT(*),1) AS emergency_rate_pct,
                ROUND(100.0*SUM(CASE WHEN ICU_admission = 'true' THEN 1 ELSE 0 END)/COUNT(*),1) AS icu_rate_pct
            FROM fact_encounter
            GROUP BY 1 ORDER BY 1
            """,
        ),
        (
            "Patient 360: individual patient deep-dive (top spender)",
            """
            WITH patient_encounters AS (
                SELECT
                    patient_id,
                    COUNT(encounter_id) AS total_encounters,
                    COUNT(DISTINCT primary_diagnosis_id) AS unique_diagnoses,
                    COUNT(DISTINCT attending_provider_id) AS providers_seen,
                    SUM(total_charges) AS lifetime_charges,
                    SUM(patient_payment) AS total_patient_paid,
                    MAX(encounter_date) AS last_encounter_date,
                    AVG(length_of_stay) AS avg_los,
                    ROUND(100.0*SUM(CASE WHEN readmission_30day = 'true' THEN 1 ELSE 0 END)/COUNT(encounter_id),1) AS readmission_rate_pct
                FROM fact_encounter
                GROUP BY patient_id
            ),
            patient_claims AS (
                SELECT
                    patient_id,
                    COUNT(claim_id) AS total_claims,
                    SUM(CASE WHEN status = 'Paid' THEN paid_amount ELSE 0 END) AS total_insurance_paid
                FROM fact_claim
                GROUP BY patient_id
            )
            SELECT
                p.first_name || ' ' || p.last_name AS full_name,
                p.age,
                p.gender,
                p.city || ', ' || p.state AS location,
                p.insurance_type || ' / ' || p.coverage_type AS insurance,
                p.account_status,
                p.smoking_status,
                p.bmi,
                COALESCE(e.total_encounters, 0) AS total_encounters,
                e.unique_diagnoses,
                e.providers_seen,
                COALESCE(c.total_claims, 0) AS total_claims,
                ROUND(COALESCE(e.lifetime_charges, 0), 0) AS lifetime_charges,
                ROUND(COALESCE(e.lifetime_charges, 0)*1.0/NULLIF(e.total_encounters,0), 0) AS avg_charges_per_encounter,
                ROUND(COALESCE(c.total_insurance_paid, 0), 0) AS total_insurance_paid,
                ROUND(COALESCE(e.total_patient_paid, 0), 0) AS total_patient_paid,
                e.last_encounter_date,
                ROUND(COALESCE(e.avg_los, 0), 1) AS avg_los,
                COALESCE(e.readmission_rate_pct, 0) AS readmission_rate_pct
            FROM dim_patient p
            LEFT JOIN patient_encounters e ON e.patient_id = p.patient_id
            LEFT JOIN patient_claims c ON c.patient_id = p.patient_id
            ORDER BY lifetime_charges DESC NULLS LAST LIMIT 10
            """,
        ),
    ]

    for name, sql in queries:
        print(f"\n{'─' * 60}")
        print(f"  {name}")
        print("─" * 60)
        result = await server.call_tool("execute_sql", {"sql": sql.strip()})
        r = parse_result(result)
        if r.get("ok"):
            rows = r["result"]["rows"]
            cols = list(rows[0].keys()) if rows else []
            print(f"  columns: {cols}")
            for row in rows[:8]:
                print(f"  {row}")
        else:
            print(f"  ERROR: {str(r.get('error', r))[:300]}")

    # ── Step 4: validate_business_questions ────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 4 — VALIDATE BUSINESS QUESTIONS")
    print("=" * 60)
    bqs = [
        "How many active patients do we have?",
        "What is the average patient age?",
        "Which diagnosis has the most encounters?",
        "What is the overall claim denial rate?",
        "Which provider has the highest patient volume?",
    ]
    result = await server.call_tool("validate_business_questions", {"questions": bqs})
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        for bq in r["result"].get("results", []):
            print(f"  Q: {bq.get('question', '')[:60]}")
            print(f"    answered: {bq.get('answered')}  |  SQL: {str(bq.get('sql', ''))[:80]}")


if __name__ == "__main__":
    asyncio.run(run())
