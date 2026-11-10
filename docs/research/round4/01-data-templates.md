# Round 4, memo 01: sources for the section 2d claims in five data templates (CB-205)

Date: 2026-11-10. Contract h-20261110-605357. Claims come from docs/review/2026-11-10-templates.md lines 106-113; template text from hr/rack/data.jsonl lines 3, 5, 8, 9, 10.

## Answer

Confidence: medium. Most mechanism claims (leakage, group splits, baselines, hybrid search, licences, accepted-name keys, uncertainty fields) have a primary source. Three things have none: every "drift" line (that a model does X by default), the "check the test's assumptions and switch to an assumption-free method" step (M2 of statistical-tester), and several "so that" rationales, which are the template's own reasoning. Drift lines need relabelling as observed failure modes or estimates, as the review already proposed for areas without Claude-specific evidence (templates.md:103).

Method note. Quotes are exact where I read the page myself (marked "read"). Where the fetch tool was blocked and I only have a search-engine summary, the entry says "secondary" and the quote is a paraphrase, not a verbatim sentence. Quotes are short because the fetch tool limits quoted length.

## statistical-tester (data:3)

| Claim | Verdict | Source and quote |
|---|---|---|
| M1 write hypothesis and test before results, chosen from the design | supported (the rationale; the template's "paired or independent, counts or measures" is the template's own) | Gelman and Loken, "The garden of forking paths", 2013, https://sites.stat.columbia.edu/gelman/research/unpublished/p_hacking.pdf (read). Abstract: "...where the details of data selection and analysis were not pre-specified and, as a result, were contingent on data." Section 1.2 defines procedure 2 as a "Classical test pre-chosen from a set of possible tests ... with preregistered". |
| M2 check assumptions in the script, switch to a method without them when they fail | no source found | Not found in the pages I read. Unconfirmed. Candidate to look up: SciPy or NIST e-Handbook pages on normality or variance checks. |
| M3 effect size with interval beside p | supported | ASA statement, March 2016, press release at https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf (read; the file is the ASA news release summarising the statement, not the full statement). Principle 5: "A p-value, or statistical significance, does not measure the size of an effect or the importance of a result." It also lists methods "that emphasize estimation over testing such as confidence, credibility, or prediction intervals". |
| M3 correct for the number of comparisons | partly | Same ASA release, principle 4: "Proper inference requires full reporting and transparency." It names "false discovery rates" among alternatives. The release does not say "correct for multiplicity" in so many words; the full statement (https://www.tandfonline.com/doi/full/10.1080/00031305.2016.1154108) returned 403 so I did not read it. Secondary: a JNCI article, https://pmc.ncbi.nlm.nih.gov/articles/PMC5017929 (read), quotes a panelist advising researchers to "limit the number of hypotheses to be tested to a realistic number that doesn't increase the false discovery rate". |
| Drift: "run several tests and report the one that came out significant" as a model default | partly for people; no source found for the model | Gelman and Loken, section 1.2, procedure 4 is exactly this: "performing J tests and then reporting the best result". But the same section says they see "no evidence" that researchers do this, and argues the likelier problem is procedure 3, a single test chosen after seeing the data. Nothing I found documents it as a Claude default. |

Suggested rewording of the drift: "Risk: choose the test after seeing the data, or run several and report the one that came out significant (Gelman and Loken, 2013). Instead: pre-state one test per question, report every test run, and adjust for their number." Label it an agent failure mode to watch for, not an observed default.

Contrary note: Gelman and Loken say deliberate fishing is not the main route to false positives. A template that only guards against "report the significant one" misses the forking-paths case. M1 covers it, which is the better-sourced step.

## spreadsheet-engineer (data:5)

| Claim | Verdict | Source and quote |
|---|---|---|
| M3 "formulas written by a script carry no computed result until then" | partly | openpyxl 3.1 tutorial, https://openpyxl.readthedocs.io/en/3.1/tutorial.html (read). On `data_only`: "controls whether cells with formulae have either the formula (default) or the value stored" (the sentence continues "the last time Excel read the sheet"). The docs do not say in terms that a file written by openpyxl has no cached value. That comes from the openpyxl maintainer on the users list, via a search-engine summary (secondary, unverified): a file created by openpyxl "probably never had its formulas evaluated, so no cached value exists" (paraphrase); `data_only=True` then returns None. |
| M2 check cells that must equal zero (row totals vs column totals; parts vs whole) | partly | EuSpRIG proceedings paper "Checks and Controls in Spreadsheets", https://arxiv.org/pdf/0908.1186 (secondary, via search summary; not opened). It describes the cross-foot check, comparing the grand total of column sums with the sum of row totals, with an IF formula that flags a mismatch. Contrary detail from https://exceluser.com/?p=2510 (secondary, practitioner article, summary only): Excel sums of decimals rarely compare exactly, so a check should use rounding or a tolerance. |
| Drift: "computing in code and pasting values" as a model default | no source found | No documentation of this as a Claude default found. Unconfirmed. |

Suggested rewording of M2: "Add check cells that should come to zero within a rounding tolerance (row totals versus column totals, sum of parts versus whole)..." Suggested M3: "...because a workbook written by a script such as openpyxl stores formulas without cached results; the stored value is whatever Excel last saved (openpyxl docs, `data_only`)." Drift: label as an observed failure mode.

## biodiversity-data-integrator (data:8)

| Claim | Verdict | Source and quote |
|---|---|---|
| M1 resolve names to a backbone; store accepted name, key, name as supplied | supported (mechanism) | GBIF API model, https://gbif.github.io/gbif-api/apidocs/org/gbif/api/model/checklistbank/NameUsageMatch.html (read). `getAcceptedUsageKey()`: "The key of the accepted name usage in case the matched usage was a synonym." `getUsageKey()`: "The name usage key of the name usage that has been matched." Status values: accepted, synonym, doubtful. |
| M1 "synonyms otherwise split one species in two" | partly | Inference from the above; no source states it. A GBIF forum answer (secondary, via search summary: https://discourse.gbif.org/t/understanding-gbif-taxonomic-keys-usagekey-taxonkey-specieskey/3045) says the usage key matches the name searched and the accepted key differs for a synonym, so occurrences of the accepted species need the accepted key. Same search found a forum thread (https://discourse.gbif.org/t/interpretation-of-species-usagekey-synonyms-when-synonym-names-resolve-to-different-accepted-taxa/6410) warning that the synonyms endpoint can return names that resolve to a different accepted taxon. The GBIF backbone FAQ returned 403. |
| M2 keep coordinate uncertainty, basis of record, date and source | supported | Darwin Core terms, https://dwc.tdwg.org/terms/ (read). `coordinateUncertaintyInMeters`: "A horizontal distance (in meters) from a given dwc:decimalLatitude and decimalLongitude" (the rest of the definition was cut off in my read). Also "Zero is not a valid value for this term." `basisOfRecord`: "The specific nature of the data record." That a specimen and a casual photo differ is the template's inference; I did not read the basisOfRecord vocabulary values (unconfirmed). |
| M3 treat an identification score as a candidate; check against occurrence records | partly | Pl@ntNet API docs, https://my.plantnet.org/doc/api/identify (my fetch got 503; secondary, via search summary): results are "ordered by decreasing confidence score", scores between 0 and 1, and no calibration or reliability guidance was found. So "candidate, not fact" is consistent with the docs, but the occurrence-plausibility check is practice advice with no source. eBird docs not checked. |
| M4 "attribution duties travel with the data" | supported | GBIF training, https://training.gbif.org/en/data-use/gbif-mediated-data-principles (read). "CC0 - no conditions for use", "CC-BY - use with attribution", and "CC-BY-NC - non-commercial use with attribution." Also: "even if the publishers have waived conditions for use, attribution is expected" and "images are not subject to the same licence that is applied to the dataset." Per-dataset licence is supported: publishers assign one licence to each occurrence dataset. |
| M4 read each service's current quota and cache responses | no source found | Not checked for GBIF or Pl@ntNet quota pages. Unconfirmed. |
| Drift: "trusting the top identification result" as a model default | no source found | No source documents this as a Claude default. |

Suggested rewording of M4: "...record the licence per dataset and keep the dataset citation, because CC BY and CC BY-NC require attribution and GBIF expects it even under CC0; images may carry different terms." Drift: label as a failure mode to guard against.

## ml-experiment-runner (data:9)

| Claim | Verdict | Source and quote |
|---|---|---|
| M1 split grouped by entity to prevent leakage | supported | scikit-learn cross-validation guide, https://scikit-learn.org/stable/modules/cross_validation.html (read). "GroupKFold is a variation of K-fold which ensures that the same group is not represented in both testing and training sets." Also "The i.i.d. assumption is broken if the underlying generative process yields groups of dependent samples." |
| M1 grouped by time | no source found | I did not read a time-split source (e.g. TimeSeriesSplit). Unconfirmed. |
| M1 leakage in general | supported | scikit-learn common pitfalls, https://scikit-learn.org/stable/common_pitfalls.html (read): "Data leakage occurs when information that would not be available at prediction time is used when building the model." Kapoor and Narayanan, https://arxiv.org/abs/2207.07048 (read as a summary only, no verbatim quote): leakage found in 17 fields affecting 329 papers, with a taxonomy of 8 leakage types. |
| M2 trivial baseline | supported | scikit-learn DummyClassifier, https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyClassifier.html (read): "This classifier serves as a simple baseline to compare against other more complex classifiers." Its own example gives a dummy score of 0.75 on a 3-to-1 class split. |
| M2 "a high score can still lose to doing nothing" | partly | The 0.75 dummy score above is an illustration, not a statement. Kapoor and Narayanan (summary) report that complex models claimed to beat logistic regression did not, once leakage was fixed. That supports the idea without saying it in these words. |
| M4 touch the test set once, for the final model | partly | scikit-learn cross-validation guide (read): "A test set should still be held out for final evaluation" and "...when the experiment seems to be successful, final evaluation can be done on the test set." Also: "knowledge about the test set can 'leak' into the model and evaluation metrics no longer report on generalization performance." The word "once" is not on either page. A claimed Hastie et al. "vault" quotation came only from an aggregator (aiwiki.ai) and I could not confirm it in the book: unconfirmed. |
| Drift: "best of many runs ... scored on data used for tuning" as a model default | partly | The mechanism is sourced by the "leak" quote above; nothing shows it is a Claude default. |

Suggested rewording of M4: "Use the test set only for the final evaluation of the chosen model, so model selection does not tune to it." Drift: label as a failure mode; cite the scikit-learn page for the mechanism.

## rag-index-builder (data:10)

| Claim | Verdict | Source and quote |
|---|---|---|
| M1/M4 golden set written first; gate on recall@k | partly | Anthropic, "Introducing Contextual Retrieval", https://www.anthropic.com/news/contextual-retrieval (read). It evaluates with a question set per domain and defines its metric ("1 minus recall@20") as one that "measures the percentage of relevant documents that fail to be retrieved within the top 20 chunks". This shows recall@k on a question set is a standard measure. "Written before building" and "gate on it" are not in the post; no source found for those. |
| M2 chunk along structure with parent pointers | partly | Anthropic (read): "The choice of chunk size, chunk boundary, and chunk overlap can affect retrieval performance." LangChain's ParentDocumentRetriever, which retrieves small chunks and then their parent documents (secondary; docs page redirected and I only have a search summary; python.langchain.com/docs/how_to/parent_document_retriever). No source found for splitting by headings specifically. |
| M3 exact names and codes are missed by embeddings alone | supported | Anthropic (read): "While embedding models excel at capturing semantic relationships, they can miss crucial exact matches." It recommends "combining the embeddings and BM25 techniques" and merging with rank fusion. |
| Drift: "fixed-size chunks, vector search only, demo query as the test" as a model default | no source found | Anthropic does not say this is a default. Unconfirmed. |

Suggested rewording of M3: "Combine keyword (BM25) and vector search, because embeddings can miss exact matches such as names and error codes (Anthropic, Contextual Retrieval)." M1 and M4: keep, but cite Anthropic only for the recall@k metric and call the "write it first" rule the template's own practice. Add a `sources` entry for rag-index-builder: it cites no 04 area (templates.md:113).

## Not reached or not checked

- Blocked (HTTP 403): tandfonline ASA full statement, gbif.org terms and FAQ, SAGE Simmons et al. 2011, Cell Patterns Kapoor paper. Pl@ntNet docs returned 503. openpyxl simple_usage pages 404.
- Read only as search-engine summaries (secondary): the openpyxl maintainer remarks, the GBIF forum threads, the Pl@ntNet docs, the EuSpRIG paper, the exceluser.com article, LangChain ParentDocumentRetriever, the Hastie et al. "vault" line.
- Not searched: eBird docs, service quota pages, time-based splits, assumption-checking references, Simmons et al. beyond a summary (its abstract was seen only via a search summary and is not used as a verdict basis).
- No source was found for any claim that a Claude model defaults to the drift behaviours. I did not test this.

END OF MEMO
