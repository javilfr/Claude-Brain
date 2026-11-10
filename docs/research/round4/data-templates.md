# Methods for five thin data templates (research date 2026-11-10)

For the template review in `docs/review/templates-2026-11-10.md`. It covers the five data templates whose sources pointed at round 3 areas that do not treat their subject: biodiversity-data-integrator, ml-experiment-runner, rag-index-builder, spreadsheet-engineer and statistical-tester.

Tags: [F] fetched and read this session, with the quoted words found on the page. [S] seen only as an abstract. [I] my inference from the fetched material, not stated by the source. Numbers below are copied from the page; none is rounded.

## Answer first

Each template already had the right shape. What it lacked was the one practice a capable model skips in that area, and a source for it:

- Biodiversity: a name match can come back fuzzy or at a higher rank, and the template stored whatever came back. Store the match type and accept only exact species-rank matches without review.
- ML experiments: leakage through preprocessing fitted on all the data. The split was fixed, but the scaler was not.
- RAG index: "combine keyword and vector search" was a fixed recipe. The evidence supports measuring BM25 alone as the baseline and keeping each further component only when recall at k rises.
- Spreadsheets: the check was static. LLM agents fail at "dynamic correctness", meaning results that do not follow when an input changes. So a check should change inputs and watch the results move.
- Statistics: the method was sound. It gains a named correction procedure and the ASA reason for reporting every test.

## 1. Biodiversity data (GBIF, Pl@ntNet, Darwin Core)

- GBIF's species match returns more than a name. A live call for *Quercus robur* returned `"status":"ACCEPTED","confidence":97,...,"matchType":"EXACT"`, plus alternatives that included a `"SYNONYM"` and two `"DOUBTFUL"` names for the same canonical name [F https://api.gbif.org/v1/species/match?name=Quercus%20robur&verbose=true]. [I] A join on the name string merges these. A stored `usageKey` with its `matchType` keeps them apart and shows which matches need review. The API also has fuzzy and higher-rank match types. Those come from my background knowledge and were not seen in this response.
- Coordinate uncertainty: Darwin Core defines `coordinateUncertaintyInMeters` as "the smallest circle containing the whole of the dcterms:Location. Zero is not a valid value for this term." `basisOfRecord` is "The specific nature of the data record" [F https://dwc.tdwg.org/terms/]. [I] A zero uncertainty is therefore a data defect and should not be read as a precise point.
- Quality flags: "More than 60 issues and flags have been created to deal with common data quality problems. Data users may use these flags to exclude occurrences from their analysis". Examples include "Zero coordinate", "Country coordinate mismatch" and "Geodetic datum assumed WGS84" [F https://techdocs.gbif.org/en/data-use/occurrence-issues-and-flags].
- Citation: "Under the terms of the GBIF data user agreement, users who download data agree to cite a DOI" [F https://techdocs.gbif.org/en/data-use/citation]. Download requests return a key, and the DOI appears "once the download is ready" [F https://techdocs.gbif.org/en/data-use/api-downloads]. [I] An app that only calls the search API has no download DOI, so attribution has to be recorded per dataset.
- Pl@ntNet identification: the service returns "the list of the most likely species as well as a confidence score for each of them". "Identification performance varies from one species to another and depends mainly on the number of images illustrating them in the training database". One request takes 1 to 5 images of a single plant [F https://my.plantnet.org/doc/getting-started/introduction]. Quota: "free up to 500 identifications per day" [F https://my.plantnet.org/pricing, read 2026-11-10; it will change, so a template should not carry the number].
- Not reached: eBird API terms (403 from birds.cornell.edu). The Postman API page returned 3 words to `curl` because it renders in the browser. The same failure would hit any helper that fetches docs with `curl`.

## 2. ML experiments

- Leakage is common in published work: "we find 17 fields where errors have been found, collectively affecting 329 papers", with "a fine-grained taxonomy of 8 types of leakage" [S abstract, Kapoor and Narayanan, https://arxiv.org/abs/2207.07048].
- Preprocessing leakage: "it is important that these transformations are only learnt from the training data"; "Never include test data when using the fit and fit_transform methods" [F https://scikit-learn.org/stable/common_pitfalls.html]. The template fixed the split but said nothing about scalers, imputers or encoders.
- Related rows: "GroupKFold is a variation of K-fold which ensures that the same group is not represented in both testing and training sets". For time series, KFold and ShuffleSplit "would result in unreasonable correlation between training and testing instances" [F https://scikit-learn.org/stable/modules/cross_validation.html]. This confirms the template's existing first method line.
- Baselines: "a simple sanity check consists of comparing one's estimator against simple rules of thumb", for example `most_frequent` and `mean` [F https://scikit-learn.org/stable/modules/model_evaluation.html, section Dummy estimators]. This confirms the existing baseline line.

## 3. RAG index

- Lexical first: on BEIR (18 datasets, 10 systems), "BM25 is a robust baseline", while dense retrieval models "often underperform other approaches" out of domain [S abstract, https://arxiv.org/abs/2104.08663].
- Hybrid and the metric: Anthropic writes that embeddings "can miss crucial exact matches" such as "Error code TS-999". Its evaluation used "1 minus recall@20". Contextual Embeddings plus Contextual BM25 "reduced the top-20-chunk retrieval failure rate by 49% (5.7% → 2.9%)", and adding reranking reached "67% (5.7% → 1.9%)" [F https://www.anthropic.com/news/contextual-retrieval]. These are vendor-measured results on Anthropic's own sets.
- [I] Together these support a gate: measure recall at k for BM25 alone, then add vectors, context or a reranker only when the golden-set number rises. A fixed hybrid recipe does not follow from them. Neither source studies golden questions written from the chunks. That pitfall stays as reasoning, unsourced.

## 4. Spreadsheets

- Errors are the norm: "Fifteen years of research studies have concluded unanimously that spreadsheet errors are both common and non-trivial... only one technique, cell-by-cell code inspection, has been demonstrated to be effective" [S abstract, Panko, https://arxiv.org/abs/0802.3457].
- LLM agents: on BlueFin (131 finance spreadsheet tasks), "the strongest LLMs achieving less than 50% average scores across tasks -- models exhibit particular weaknesses in dynamic correctness" [S abstract, https://arxiv.org/abs/2605.30907]. SpreadsheetBench grades each instruction against "multiple spreadsheet files... with varying values" to catch solutions that only fit one file [S abstract, https://arxiv.org/abs/2406.14991].
- Formula values: openpyxl's `data_only` "controls whether cells with formulae have either the formula (default) or the value stored the last time Excel read the sheet" [F https://openpyxl.readthedocs.io/en/stable/tutorial.html]. [I] A workbook written by a script holds no stored values until a spreadsheet engine recalculates it, which confirms the template's recalculation line. LibreOffice's documented `--convert-to` option is one headless route [F https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html]. That it recalculates on conversion is my background knowledge, not confirmed.
- [I] The new check: change two inputs, recalculate, and compare dependent cells with the independent computation. A pasted value passes a static check and fails this one.

## 5. Statistics

- ASA statement, principles 4 and 5: "Proper inference requires full reporting and transparency" and "A p-value, or statistical significance, does not measure the size of an effect or the importance of a result" [F https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf]. These support the template's every-test-reported drift and its effect-size line.
- Multiple comparisons: SciPy's `false_discovery_control` gives Benjamini-Hochberg ('bh') and the "more conservative" Benjamini-Yekutieli ('by'), which controls the FDR "even when the p-values are not from independent tests" [F https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html].
- LLM analysis can be p-hacked: "a researcher can tune the prompts, decoding parameters, or output format until a desired result is reached". Preregistration blocked transfer of the hack "in 73.9% and 72.7% of cases" in two tasks [S abstract, https://arxiv.org/abs/2606.27687]. [I] A helper that runs analyses itself is in the same position, so writing the test before seeing results is the control that matters.

## What this changes in the rack

| Template | Change | Basis |
|---|---|---|
| biodiversity-data-integrator | store match type and key; review non-exact matches; record per-dataset licence and download DOI | §1 [F] |
| ml-experiment-runner | fit every preprocessing step on the training split only | §2 [F] |
| rag-index-builder | BM25 baseline first, add components only when recall at k rises | §3 [S][F] |
| spreadsheet-engineer | change inputs and confirm dependent results follow | §4 [S][I] |
| statistical-tester | name Holm or Benjamini-Hochberg (Benjamini-Yekutieli for dependent tests) | §5 [F] |

## Not checked

- eBird terms and quotas (blocked), GBIF API rate limits (no page found at the guessed address), and the Pl@ntNet terms page.
- The full papers behind every [S] item. Their numbers are copied from the abstracts.
- Whether any of these defaults actually appears in Claude's output on these tasks. No run with and without the template was made.

END OF MEMO
