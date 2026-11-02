# Response to the Editorial Office

**Manuscript:** AutoResearch-Ledger: Transactional Revision Integrity for Executable Research Agents

We thank the editorial office for the careful pre-review check. Each point is answered below.

---

**Comment 1: Author order and affiliation numbering.**

**Response:** We apologise for the mismatch. The manuscript lists four authors in this order: Rajesh Kumar¹ (first author), Waqar Ali²˒\* (second and corresponding author), Nikesh Lagun³˒⁴ and Shaoning Zeng⁵. It has five numbered affiliations. The corresponding author is Waqar Ali, affiliation 2 (College of Science, Mathematics and Technology, Wenzhou-Kean University, Wenzhou, China; waqar.uestc@yahoo.com). We have corrected the submission system so that the author order, the five affiliations and the corresponding author's affiliation (2) match the manuscript exactly.

---

**Comment 2: Abstract and Figure 1 claims (HumanEval, MBPP, SciCode subset; "Completion improved by 41%").**

**Response:** We agree that these claims were not supported by the reported evidence, and we have removed them. The benchmark sentence and the comparative performance claims came from an earlier, broader description of the AutoResearch system. They do not belong to the study reported here. The graphical abstract that showed "Completion improved by 41%" has also been removed; Figure 1 is now the TRL architecture diagram, which contains no performance numbers. The revised abstract reports only results that appear in the body: 815/815 oracle agreement on synthetic fixtures, 13 historical revisions carried through the tracked proxy, 6/6 transaction fault-injection checks, the 10/10 structural pilot and 206/206 software tests. It now also states plainly that code generation (HumanEval, MBPP, SciCode), citation validity and end-to-end workflow completion were not evaluated, and that we make no comparative claims about them.

---

**Comment 3: The abstract's "higher execution success, citation validity, claim support and workflow completion" conflicts with Table 2.**

**Response:** We agree, and we have corrected the abstract (see the response to Comment 2). The statement "Experimental evaluation demonstrates that AutoResearch achieves higher execution success rates…" has been deleted. Table 2 (evidence hierarchy) now has an explicit row: "Code-generation, citation-validity and end-to-end workflow benchmarks — not evaluated." The abstract, Table 2, the Results and the Discussion now describe the same evidence. We have also removed from the Supplement two legacy tables: executor HumanEval/MBPP results and a citation-annotation comparison. Those results came from an earlier system evaluation that was not run under a matched protocol, and they are not part of this study's evidence.

---

**Comment 4: The six required declarations.**

**Response:** All six statements now appear at the end of the article: Acknowledgement, Funding Statement, Author Contributions, Availability of Data and Materials, Ethics Approval and Conflicts of Interest. The study received no external funding, and the authors declare no conflicts of interest. Ethics approval is not applicable, because the study uses only public open-source software repositories and synthetic fixtures; the human-audit study is a protocol only and has not been conducted. Code and validation materials are available at https://github.com/raja21068/ResearchLedger.

---

**Comment 5: Reference [1] has negative PubPeer comments.**

**Response:** Thank you. We have removed the former reference [1] (Lu et al., *Nature* 2026, "Towards end-to-end automation of AI research"). Its preprint successor (Yamada et al., *AI Scientist-v2*, arXiv) has also been removed. In their place we cite peer-reviewed research-agent systems:
- Boiko et al., *Nature* 624, 570–578 (2023), doi:10.1038/s41586-023-06792-0
- Bran et al., *Nature Machine Intelligence* 6, 525–535 (2024), doi:10.1038/s42256-024-00832-8
- Swanson et al., *Nature* (2025), doi:10.1038/s41586-025-09442-9

None of our claims depended on the removed reference.

---

**Comment 6: Non-peer-reviewed sources.**

**Response:** We have reviewed every reference. Two preprints have been removed:
- AI Scientist-v2 (arXiv:2504.08066)
- Rasheed et al., "From Fluent to Verifiable" (arXiv:2602.13855); the peer-reviewed CHI 2026 PaperTrail study now covers that point

Four preprints remain: ScientistOne, EviGraph, ARIS and the Transactional Continuity Kernel. They are the closest contemporaneous systems to our contribution, and none has a peer-reviewed version yet. We keep them only for positioning and novelty-boundary comparison (Supplement S8). They are marked "Preprint; not peer reviewed" in the reference list, and the Related Work section now says explicitly that we draw no evidential support from them. The W3C PROV-DM entry is a formal W3C Recommendation (a standards document), not a preprint. All other references are peer-reviewed journal articles, conference papers or established books.
