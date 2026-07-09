# Synthetic Dataset Commercial License Agreement

**Template — customize bracketed fields before use.**

---

## ADP Synthetic Dataset License

**Dataset:** [Dataset Name, e.g. "Retail Seasonal Pro — 1M Rows"]  
**SKU:** [e.g. ADP-RETAIL-1M]  
**Licensor:** Yogesh Khangode / TMDC.io ("Licensor")  
**Licensee:** [Purchaser name or "the individual or organization completing purchase"]  
**Effective date:** [Date of purchase]  
**Version:** 1.0

---

### 1. Grant of license

Subject to payment and compliance with this Agreement, Licensor grants Licensee a **non-exclusive, non-transferable, worldwide license** to:

(a) **Use** the Dataset (data files, spec, documentation) for internal business purposes, including development, testing, demonstration, analytics, machine learning training and evaluation, and quality assurance.

(b) **Modify** the Dataset and **regenerate** data from the included `spec.yaml` using ai-data-platform (ADP), solely for Licensee's internal use, where regeneration rights are explicitly included in the SKU description.

(c) **Create derivative works** (dashboards, models, reports, applications) built on the Dataset, and **deploy** such derivatives in production, provided no raw Dataset files are redistributed.

---

### 2. Synthetic data warranty

Licensor represents that:

(a) The Dataset was **generated synthetically** using ai-data-platform from declarative specifications. **No real personal data** from production systems was used as input to generate this Dataset.

(b) The Dataset is intended to contain **no real personally identifiable information (PII)**. Names, emails, addresses, and identifiers are algorithmically generated and do not correspond to real individuals.

(c) A **quality report** is included documenting structural checks (foreign key integrity, distribution checks, seasonality validation where applicable). The quality score and check results are provided **as-is** for informational purposes.

---

### 3. Restrictions

Licensee shall **not**:

(a) **Resell, sublicense, redistribute, or publish** the Dataset (or substantial portions) to third parties, except as embedded aggregates in deployed applications where raw rows are not extractable.

(b) **Represent the Dataset as real production or customer data** in any external-facing context without clear disclosure that data is synthetic.

(c) **Use the Dataset** to attempt re-identification of any individual or to train systems intended to deanonymize real data.

(d) **Remove or alter** license notices in included documentation.

(e) **Share regeneration artifacts** (spec.yaml, generated files) outside Licensee's organization unless Licensee holds an enterprise license explicitly permitting affiliate use.

---

### 4. Disclaimer of warranties

THE DATASET IS PROVIDED **"AS IS"** WITHOUT WARRANTY OF ANY KIND. LICENSOR DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

Licensee acknowledges that:

(a) Synthetic data **may not perfectly mirror** real-world statistical properties, edge cases, or business rules of any specific production environment.

(b) The Dataset is suitable for **development, testing, demonstration, and prototyping**. Licensee is solely responsible for validating fitness before use in regulated, safety-critical, or production decision systems.

(c) Quality scores and reports are **automated structural checks**, not guarantees of business accuracy, regulatory compliance, or model performance.

---

### 5. Limitation of liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, LICENSOR'S TOTAL LIABILITY ARISING FROM THIS AGREEMENT SHALL NOT EXCEED THE **AMOUNT PAID BY LICENSEE FOR THIS DATASET**.

IN NO EVENT SHALL LICENSOR BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOST PROFITS, DATA LOSS, OR REGULATORY PENALTIES, EVEN IF ADVISED OF THE POSSIBILITY.

---

### 6. Compliance

(a) Licensee is responsible for determining whether use of synthetic data satisfies applicable laws (GDPR, HIPAA, CCPA, etc.) in Licensee's jurisdiction and use case.

(b) This license **does not constitute legal advice**. Licensee should consult qualified counsel for regulated industries (healthcare, finance, government).

(c) Where Licensee operates in the EU, Licensee acknowledges the Dataset is synthetic and not personal data as defined in GDPR Article 4(1), **provided** Licensee does not combine it with real personal data in a manner that enables identification.

---

### 7. Intellectual property

(a) **Dataset files** — Licensed as above; Licensor retains ownership of the generation methodology and spec.

(b) **`spec.yaml` and ADP tooling** — The spec file is licensed for regeneration as described in Section 1. ai-data-platform software is separately licensed under Apache-2.0 (see github.com/Yogi776/data-generation-sdk).

(c) **Licensee derivatives** — Licensee owns dashboards, models, and applications built on the Dataset, subject to Section 3 restrictions.

---

### 8. Term and termination

(a) This license is **perpetual** for the purchased SKU unless terminated under (b).

(b) Licensor may terminate if Licensee breaches Section 3 and fails to cure within 30 days of written notice.

(c) Upon termination, Licensee must **cease use and delete** copies of the Dataset, except where retention is required by law.

---

### 9. Refunds

(a) Licensee may request a refund within **14 days** of purchase if the Dataset fails to match the published SKU description (tables, row counts, formats).

(b) Refunds are **not available** after substantial use (e.g. integration into production systems) or after the 14-day window.

(c) Licensor encourages buyers to download the **free 1K-row sample** before purchase to evaluate structure and quality.

---

### 10. Governing law

This Agreement is governed by the laws of **[India / State of Delaware, USA — choose one]**, without regard to conflict of law principles. Disputes shall be resolved in the courts of **[jurisdiction]**.

---

### 11. Contact

**Licensor:** Yogesh Khangode  
**Email:** yogesh.khangode@tmdc.io  
**Product:** ai-data-platform — https://github.com/Yogi776/data-generation-sdk

---

## Quick reference (for storefront listing)

| Right | Included |
|-------|----------|
| Internal business use | ✅ |
| Demo / sales presentations | ✅ |
| ML training & evaluation | ✅ |
| Modify & regenerate (if SKU includes spec) | ✅ |
| Production apps (derivatives, not raw data) | ✅ |
| Resell or redistribute raw data | ❌ |
| Represent as real customer data | ❌ |
| Perpetual license | ✅ |
| Refund window | 14 days |

---

*This template is provided for informational purposes and does not constitute legal advice. Have qualified counsel review before use in commerce.*
