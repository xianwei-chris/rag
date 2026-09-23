# Synthetic Internal Policy Addendum
## Internal Use of Patient-Level Data and RAG Systems

**Document status:** Synthetic document for assessment purposes only  
**Effective date:** 1 July 2026  
**Applies to:** Internal analytics, data platform, AI/ML, and operational reporting use cases

## 1. Purpose

This addendum sets out internal rules for using patient-level data, de-identified data, anonymised data, and derived analytics outputs.

It is intended to supplement the public PDPC guidance provided in the document pack. Where this addendum is more specific than the general guidance, candidates should treat this addendum as the internal policy position for this assessment.

## 2. Key Definitions

**Patient-level data** means data relating to an individual patient, including appointment records, billing records, insurance records, treatment records, medical history, contact details, identifiers, or event-level activity.

**Direct identifiers** include patient name, NRIC or FIN, passport number, medical record number, phone number, email address, residential address, policy number, and any system ID that can directly link back to a patient.

**De-identified data** means data where direct identifiers have been removed or replaced, but where re-identification may still be possible.

**Anonymised data** means data that has been processed so that individuals cannot reasonably be identified, taking into account other information likely to be available and the risk of re-identification.

**Broad internal reporting** means reports, dashboards, extracts, or summaries made available to users beyond the immediate data, clinical, operational, billing, insurance, or management team responsible for the use case.

## 3. Internal Analytics Rules

Patient-level data may be used for internal analytics only where all of the following are true:

1. there is a defined business, operational, clinical, compliance, or management purpose;
2. the use has been approved by the relevant data owner;
3. access is limited to authorised users with a valid need;
4. only the minimum necessary data is used; and
5. outputs are reviewed for identifiability before broader sharing.

Broad internal reporting should use aggregated or anonymised data wherever possible.

Patient identifiers must not be included in broad internal reports unless there is a documented operational need and approval from both the data owner and compliance representative.

## 4. Small Cell Suppression

Where a report, dashboard, extract, or analytics output contains patient-related counts, any cell with fewer than **5 patients** must be suppressed or combined with another category.

Small cell suppression is required for:

- broad internal reporting;
- management dashboards;
- external sharing;
- publication; and
- AI/ML evaluation summaries that may reveal patient-level patterns.

Small cell suppression may be waived only where there is a documented operational need, restricted access, and approval from the data owner.

## 5. External Sharing

Patient-level data must not be shared externally unless there is a valid legal, contractual, operational, patient-authorised, or approved research basis.

Before external sharing, the requester must document:

1. the purpose of sharing;
2. the recipient;
3. the data fields to be shared;
4. whether direct identifiers are included;
5. whether the data is patient-level, de-identified, anonymised, or aggregated;
6. the safeguards applied; and
7. the approval obtained.

External sharing of patient-level or de-identified data requires approval from the data owner and compliance representative.

External sharing of anonymised or aggregated data requires approval from the data owner. Compliance review is required where the data relates to sensitive conditions, rare procedures, small populations, or high-profile individuals.

## 6. Use of Data for AI/ML and RAG Systems

AI/ML and RAG systems may use patient-related data only where the purpose has been approved and access controls are enforced.

A RAG system must not retrieve or expose source passages that the user is not authorised to access.

For production RAG systems using sensitive or patient-related data, the following controls are required:

1. source-level or chunk-level access control;
2. audit logs recording user, timestamp, query, retrieved source IDs, and answer support status;
3. restrictions on logging raw patient-sensitive prompts or outputs unless approved;
4. source citations for generated answers;
5. refusal behaviour where retrieved evidence is insufficient;
6. monitoring for unsupported answers, unsafe disclosures, and prompt-injection attempts; and
7. human escalation for high-impact, ambiguous, or clinically sensitive queries.

RAG systems must not be used as the sole basis for clinical diagnosis, treatment decisions, insurance approvals, claim denials, or patient-facing medical advice unless separately approved under a formal clinical governance process.

## 7. De-identified and Anonymised Data

De-identification alone is not sufficient to treat data as outside internal data governance controls.

De-identified patient-level data should still be treated as sensitive unless a re-identification risk assessment supports a lower-risk classification.

Anonymised data may be used more broadly only where:

1. direct identifiers have been removed or transformed;
2. indirect identifiers have been assessed;
3. re-identification risk is low for the intended audience and use case;
4. small cells have been suppressed or combined where relevant; and
5. the anonymisation method and assumptions have been documented.

## 8. Retention and Review

Patient-level extracts created for analytics, testing, or AI/ML development must have a defined retention period.

Temporary extracts should be deleted once the purpose has been fulfilled unless there is a documented legal, business, audit, or research need to retain them.

Long-running dashboards, recurring reports, and production RAG indexes must be reviewed at least annually, or earlier if:

- the purpose changes;
- the audience expands;
- new data fields are added;
- external sharing is introduced;
- direct identifiers are added;
- patient-level drill-through is enabled; or
- there is a data incident or material complaint.

## 9. Examples

### Example A: Broad management dashboard

A dashboard showing monthly patient volumes by clinic and specialty may be shared broadly if it uses aggregated data and suppresses cells with fewer than 5 patients.

### Example B: Patient-level collections worklist

A billing team worklist containing patient names, invoices, contact details, and outstanding amounts may be used by authorised billing staff for collections follow-up. It should not be shared as a broad management report.

### Example C: RAG chatbot over internal policy documents

A RAG chatbot answering questions over public policy and internal governance documents may be made available to internal staff if the source documents are approved for broad internal use. If the chatbot also indexes patient-level records or restricted operational documents, retrieval must enforce user permissions.

### Example D: AI model development

A model development team may use de-identified patient-level data for approved model development if direct identifiers are removed, access is restricted, retention is defined, and re-identification risk is assessed. If anonymised or aggregated data is sufficient, patient-level data should not be used.

## 10. Approval Summary

| Use case | Minimum approval required |
|---|---|
| Broad internal aggregate reporting | Data owner |
| Broad reporting with patient-related small cells below 5 | Data owner and compliance representative |
| Restricted patient-level analytics | Data owner |
| Patient-level operational worklist | Operational owner or data owner |
| External sharing of patient-level or de-identified data | Data owner and compliance representative |
| External sharing of anonymised or aggregated data | Data owner; compliance if sensitive or high-risk |
| Production RAG over sensitive or patient-level data | Data owner, compliance representative, and system owner |
| Use of RAG for clinical, insurance, or high-impact decisions | Formal clinical or business governance approval |
