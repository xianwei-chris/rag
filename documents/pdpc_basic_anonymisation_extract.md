# PDPC Guide to Basic Anonymisation - Short Extract

Source: Personal Data Protection Commission Singapore, **Guide to Basic Anonymisation** (updated 24 July 2024).

Purpose of this extract: candidate source document for a lightweight RAG take-home assignment. This shortened version keeps the core concepts, workflow, risk ideas, and practical techniques while removing most long examples and annex detail.

Included source pages: 5, 7-8, 10-12, 14-18, 20-27, 30-32, 34-36, 38-43, 49, 52-55.

Note: This is an extract for technical assessment use. It is not legal advice and is not a substitute for the full source document.

---

## Source page 5 - Scope and limits of the guide

The guide provides an introduction and practical guidance for organisations that are new to anonymisation. It focuses on basic anonymisation and de-identification of structured, textual, non-complex datasets, such as spreadsheets or relational database tables.

The guide is not exhaustive. Organisations should consider engaging anonymisation experts, statisticians, or independent risk assessors where the dataset or risk assessment is complex. Examples of complex cases include large datasets with longitudinal records or sensitive personal data.

Implementation of the guide's recommendations does not by itself imply compliance with the PDPA. Different jurisdictions may also view anonymisation differently.

---

## Source pages 7-8 - Anonymisation versus de-identification

**Anonymisation** means converting personal data into data that cannot be used to identify any individual. PDPC treats anonymisation as a risk-based process involving both anonymisation techniques and safeguards to prevent re-identification.

**De-identification** means removing direct identifiers, such as name, address, or NRIC number. De-identification may include assigning pseudonyms.

De-identification is not the same as anonymisation. It is only the first step. A de-identified dataset may still be re-identified when combined with publicly available or easily accessible information.

**Re-identification** means identifying individuals from a dataset that was previously de-identified or anonymised.

Anonymised data is not considered personal data and is not governed by the PDPA. However, whether data is truly anonymised depends on the residual risk of re-identification.

Example: removing a user's name from a food-ordering dataset may not be enough if the remaining fields, such as date of birth, gender, company, favourite food, and favourite eatery, can be linked with public social media information.

---

## Source pages 10-12 - Basic anonymisation concepts

### Purpose and utility

The purpose of anonymisation should be clear before techniques are applied. Anonymisation reduces information in the dataset, so there is usually a trade-off between utility and re-identification risk.

Utility should not be assessed only at whole-dataset level. Some attributes may be critical and should not be generalised if accuracy is essential. Other attributes may be unnecessary for the purpose and can be removed entirely.

Organisations should also consider whether revealing the anonymisation method or level of granularity could itself increase re-identification risk.

### Reversibility

An anonymisation process is typically intended to be irreversible. However, some processes may be reversible if the organisation keeps the ability to recreate the original dataset, for example through a mapping table. In such cases, stronger safeguards are required.

### Technique choice

Different techniques suit different data types. Character masking may be more suitable for direct identifiers. Aggregation may be more suitable for indirect identifiers. Perturbation works better for continuous numerical values than for discrete values.

Techniques modify data in different ways. Some modify part of a value, some replace values across records, some replace identifiers with pseudonyms, and some remove attributes or records entirely. Techniques may also be combined.

### Inference risk

Anonymised data may still allow inference. Masking can hide characters but may reveal the length of the original value. Record order may reveal information if the recipient knows the records were collected sequentially. Inference can arise from a single attribute or from combinations of attributes.

### Subject-matter expertise

Identifiability and re-identifiability should be assessed before and after anonymisation. This requires understanding the subject matter. For healthcare data, someone with sufficient healthcare knowledge may be needed to assess whether a record is unique or re-identifiable.

Employees performing anonymisation should be trained in anonymisation principles and techniques. External help should be engaged if the necessary expertise is not available internally.

### Recipient context

The recipient matters. Their expertise, access to other data, and contractual or technical controls affect re-identification risk. Public releases require stronger anonymisation than data shared under a controlled contractual arrangement.

---

## Source page 14 - The five-step anonymisation process

The guide describes a five-step process:

1. **Know your data**
2. **De-identify your data**
3. **Apply anonymisation techniques**
4. **Compute your risk**
5. **Manage your risks**

Across all use cases, organisations should ensure:

- data minimisation: share only necessary attributes and, where possible, only an extract of the dataset;
- identifying information in the dataset should not be publicly available;
- appropriate protection and safeguards should apply to the anonymised dataset and any identity mapping table;
- generally, the less a dataset is modified, the more it needs to be protected because re-identification risk is higher.

---

## Source pages 15-17 - Common use cases

### Internal data sharing: de-identified data

Internal sharing may involve de-identified record-level data. This preserves high utility but the result is still likely to be personal data because it may be easily re-identifiable. Additional controls are needed.

Result considered anonymised: **No**.

### Internal data sharing: anonymised data

Organisations may use anonymised data instead of merely de-identified data where detailed record-level personal data is not required, the data is sensitive, or a large dataset is shared with more than one department.

Result considered anonymised: **Yes**, if the anonymisation is sufficient.

### External data sharing

External sharing may involve record-level data shared with an authorised external party for collaboration. Anonymisation techniques are used to convert personal data to non-identifying data. Additional controls are still needed, and identity mapping tables should not be shared externally.

Result considered anonymised: **Yes**, if the anonymisation is sufficient.

### Long-term retention for data analysis

Anonymisation can allow data to be kept at record level beyond the retention period for long-term analysis. Additional controls are needed. Identity mapping tables should be securely destroyed.

Result considered anonymised: **Yes**, if the anonymisation is sufficient.

### Fictitious data for development and testing

Fictitious data can be created by heavily anonymising all attributes so that records no longer match actual individuals. This may be suitable for application development and testing, but it does not retain the statistical characteristics of the original data and is not suitable for sophisticated uses such as AI model training or analytics.

Result considered anonymised: **Yes**.

---

## Source pages 18-19 - Know your data: direct identifiers, indirect identifiers, target attributes

A personal data record contains attributes with different degrees of identifiability and sensitivity.

### Direct identifiers

Direct identifiers are unique to an individual and can be used as key attributes to re-identify them. Examples include:

- name;
- email address;
- mobile number;
- NRIC number;
- passport number;
- account number;
- FIN or work permit number;
- social media username.

Direct identifiers are usually public or easily accessible and should generally be removed or pseudonymised.

### Indirect identifiers

Indirect identifiers are not unique on their own but may re-identify an individual when combined with other information. Examples include:

- age;
- gender;
- race;
- date of birth;
- address or postal code;
- job title or company name;
- marital status;
- height or weight;
- IP address;
- vehicle licence plate number;
- GPS location.

Indirect identifiers are usually modified using anonymisation techniques such as generalisation, masking, swapping, or perturbation.

### Target attributes

Target attributes contain the main utility of the dataset. They may be sensitive and can cause harm if disclosed. Examples include:

- transactions;
- salary;
- credit rating;
- insurance policy;
- medical diagnosis;
- vaccination status.

Target attributes are usually left unchanged, except when creating fictitious data.

---

## Source pages 20-21 - Step 2: de-identify your data

De-identification is always performed as part of the anonymisation process.

First, remove all direct identifiers. If the dataset includes names, NRIC numbers, email addresses, or other direct identifiers, these should be removed unless there is a justified need to preserve linkage.

Any attribute not required in the resulting dataset should be removed as data minimisation.

Pseudonyms may be assigned where there is a need to link records back to unique individuals or original records, such as for data merger, analysis of multiple records relating to the same individual, or creation of fictitious datasets where direct identifier values are required for testing.

Pseudonyms should be unique and robust. They should not be reversible by unauthorised parties through guessing or computation. If a mapping between original identifiers and pseudonyms is kept, the identity mapping table must be secured because it permits re-identification.

---

## Source pages 22-23 - Step 3: apply anonymisation techniques

After de-identification, anonymisation techniques are applied to indirect identifiers so they cannot be easily combined with other datasets to re-identify individuals. For fictitious data, techniques should also be applied to target attributes.

Techniques affect utility, so the chosen method should match the use case.

For internal anonymised data sharing or external data sharing, suggested techniques include:

- **record suppression**: remove rows, especially outliers or unique records;
- **attribute suppression**: remove columns that are not needed or too identifying;
- **character masking**: replace part of a value with symbols, such as changing `235546` to `23xxxx`;
- **generalisation**: reduce granularity, such as changing age `26` to `25-29`.

For long-term data retention, suggested techniques include suppression, masking, generalisation, and data perturbation.

For fictitious data, heavy anonymisation should be applied to all attributes, including target attributes. The resulting dataset should not resemble the original and is suitable for development/testing, but not AI model training.

After applying techniques, organisations should compute the risk. If the target k-anonymity level is not achieved, they should repeat anonymisation and risk assessment. The guide refers to k values of 3, 5, or more.

---

## Source pages 24-25 and 49 - Step 4: compute risk using k-anonymity

**k-anonymity** is a simple method to assess re-identification risk. It refers to the smallest number of identical records that can be grouped together in a dataset based on indirect identifiers.

A k-anonymity value of 1 means a record is unique. A higher k value means lower re-identification risk. A lower k value means higher risk.

Generally, only indirect identifiers are considered in k-anonymity computation. Direct identifiers should already have been removed, and pseudonyms should not be included; otherwise every record may appear unique.

The overall k-anonymity value of a dataset is usually the lowest k value among its equivalence classes, reflecting the highest-risk group. For example, if groups have sizes 2, 3, and 4, the dataset's overall k value is 2.

The guide notes that industry thresholds are generally k=3 or k=5. Where possible, a higher k should be used, especially for external sharing. A lower value such as k=3 may be used for internal sharing or long-term retention, depending on safeguards.

k-anonymity is not suitable for every dataset or complex use case. It may be less suitable for longitudinal or transactional data where the same person may appear multiple times. It also has limitations such as attribute disclosure through homogeneity attacks; l-diversity and t-closeness address some of these limitations but are outside the guide's scope.

---

## Source pages 25-27 - Step 5: manage re-identification and disclosure risks

Even after anonymisation, safeguards are needed because future technology or unknown datasets may make re-identification easier.

Organisations should document the anonymisation process, parameters used, and controls. This helps review, maintenance, fine-tuning, and audit. Such documentation should be kept securely because releasing parameters may facilitate re-identification.

The guide describes three fundamental risk types:

### Identity disclosure

Identity disclosure occurs when someone can determine, with high confidence, the identity of an individual described by a specific record. This may arise from insufficient anonymisation, linking, or pseudonym reversal.

### Attribute disclosure

Attribute disclosure occurs when someone can determine, with high confidence, that a specific attribute belongs to an individual, even if the individual's record cannot be distinguished. For example, if all clients below age 30 in a dataset have undergone a particular procedure, that procedure may be inferred for a known 28-year-old client.

### Inference disclosure

Inference disclosure occurs when someone can infer information about an individual from statistical properties of the dataset, even if that individual is not in the dataset.

For de-identified data, re-identification risk is higher because only direct identifiers have been removed. Protection is required, and any mapping tables should be secured.

For anonymised internal or external sharing, basic protection is still required. Mapping tables should not be shared with recipients. For long-term retention, mapping tables should be securely destroyed.

---

## Source pages 28-32 - Safeguards and controls

The guide suggests technical, process, and legal controls to manage re-identification and disclosure risk.

### Technical controls

Recommended controls include:

- application-level access control;
- strong passwords;
- regular user account review;
- protection of computers and storage devices;
- encryption of sensitive de-identified datasets where appropriate;
- encryption and secure handling of identity mapping tables;
- communicating decryption keys separately from exported data.

Identity mapping tables should be secured and not shared. For long-term retention, mapping tables should be removed.

### Process controls

Recommended process controls include:

- data breach management plans covering loss of datasets and mapping tables;
- central registry of shared de-identified or anonymised datasets;
- periodic re-identification reviews;
- approval of recipient and purpose;
- prohibition on unauthorised sharing or re-identification attempts;
- regular purging when purpose is fulfilled;
- periodic internal checks or audits.

### Incident management

Breach of both de-identified data and the identity mapping table is akin to breach of personal data. The organisation must assess whether the breach is notifiable and notify affected individuals and/or the Commission where required.

If de-identified data alone is breached, the organisation must assess whether the breach is notifiable because de-identified data has higher re-identification risk.

If properly anonymised data alone is lost, reporting as a notifiable breach may not be required, but the incident should still be investigated.

If only the identity mapping table is lost and the relevant datasets remain protected, the mapping table alone is not personal data, but the organisation should generate new pseudonyms and a new mapping table and investigate the incident.

### Legal controls for external sharing

For external sharing, data sharing agreements should ensure that data is only used for permitted purposes, prohibit attempts to re-identify anonymised datasets, and require third-party recipients to apply relevant protection measures.

---

## Source pages 34-36 - Selected technique: record suppression, masking, pseudonymisation

### Record suppression

Record suppression means removing an entire row. It is used to remove outlier records that are unique or fail to meet criteria such as k-anonymity. Suppression should be permanent; hiding a row is not enough if the underlying data remains accessible.

### Character masking

Character masking means replacing some characters in a value with a consistent symbol such as `*` or `x`. It is used when hiding part of the value is sufficient.

Masking must consider whether the remaining length or visible characters reveal information. Subject-matter knowledge is important. If complete masking is needed, attribute suppression may be more appropriate.

### Pseudonymisation

Pseudonymisation replaces identifying data with made-up values. It may be irreversible if original values are disposed of and the process is non-repeatable. It may be reversible if original values or mapping tables are securely kept.

Persistent pseudonyms can preserve referential integrity across datasets. However, using the same pseudonym across datasets may also enable linkage.

For reversible pseudonyms, the identity mapping table must not be shared with the recipient and should be securely kept. If encryption or hashing is used, the key, algorithm, salt, or seed must be protected.

---

## Source pages 38-43 - Selected technique: generalisation, swapping, perturbation, aggregation

### Generalisation

Generalisation deliberately reduces precision. Examples include converting age to an age band or a precise address to a broader location.

Generalisation is useful where lower precision still supports the intended purpose. Ranges should be chosen carefully: too wide reduces utility; too narrow may not reduce re-identification risk enough. Records that remain unique after generalisation may need to be suppressed or generalised further.

### Swapping

Swapping rearranges values across records so that values remain represented in the dataset but no longer correspond to the original records. It is useful when analysis only needs aggregate or intra-attribute patterns and does not require record-level relationships between attributes.

Swapping may be unsuitable if the purpose is to study relationships between attributes at record level.

### Data perturbation

Data perturbation modifies original values slightly, for example by rounding or adding noise. It is commonly used for numerical indirect identifiers such as numbers or dates where slight changes are acceptable.

Perturbation should not be used where data accuracy is crucial. The amount of perturbation should be proportionate: too little gives weak anonymisation; too much reduces utility.

### Data aggregation

Data aggregation converts record-level data into summary values such as totals or averages. It is suitable when individual records are not required.

Aggregation may need to be combined with suppression where a group has too few records. Very small groups can still reveal information about individuals.

---

## Source pages 52-55 - Simplified re-identification risk model

The guide describes a simplified model for assessing re-identification risk using k-anonymity.

A risk threshold should first be established. This reflects the level of risk an organisation is willing to accept. The threshold depends on potential harm to the individual and organisation if re-identification occurs, as well as mitigating controls.

Example thresholds provided in the guide are:

| Potential harm | Example risk threshold |
|---|---:|
| Low | 0.2 |
| Medium | 0.1 |
| High | 0.01 |

The guide uses **Prosecutor Risk**, which assumes an attacker knows a specific person is in the dataset and tries to identify which record belongs to that person.

A simple rule is:

```text
P(link individual to a single record) = 1 / record's equivalence class size
P(re-ID any record in dataset) = 1 / minimum equivalence class size in dataset
```

If a dataset is k-anonymised:

```text
P(re-ID any record in dataset) <= 1 / k
```

The overall probability of re-identification can be expressed as:

```text
P(re-ID) = P(re-ID | re-ID attempt) x P(re-ID attempt)
```

For a k-anonymised dataset:

```text
P(re-ID) = (1 / k) x P(re-ID attempt)
```

The guide considers three re-identification attempt scenarios:

1. deliberate insider attack;
2. inadvertent recognition by an acquaintance;
3. data breach.

The highest probability among these scenarios is used as `P(re-ID attempt)`.

---

## Practical summary for this document

A good answer based on this document should recognise that:

- de-identification is not the same as anonymisation;
- anonymisation is risk-based and depends on context, recipients, safeguards, and available linkage data;
- direct identifiers should generally be removed or pseudonymised;
- indirect identifiers may require generalisation, masking, perturbation, swapping, aggregation, or suppression;
- target attributes are usually preserved for utility, except in fictitious data;
- k-anonymity is useful but limited;
- mapping tables can re-identify data and must be protected or destroyed depending on use case;
- external sharing requires stronger safeguards than internal sharing;
- anonymisation decisions involve a trade-off between utility and re-identification risk.
