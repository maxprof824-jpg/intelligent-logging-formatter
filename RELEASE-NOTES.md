# Intelligent Logging Formatter 2.5 — proof-of-concept preview

This update gives author-labeled events their own five-section drafts. Start an event with `EVENT: descriptive label`; repeating the label joins its later updates. Without headings, notes remain together. The source comparison now includes suggestions and all matching original locations when a quotation repeats.

The release adds a 20-note synthetic development evaluation across five logging domains, with five legacy-pipeline comparisons and ten reserved notes that remain unused for inference. A broader training curriculum is prepared, but the released model still uses the original v2 adapter trained on 480 examples with 48 validation examples. No new candidate weights are included.

Download `intelligent-logging-formatter-tester-v2.5.zip`, extract it, run `SETUP-WINDOWS.cmd`, then `RUN-DEMO.cmd`. Windows and a compatible NVIDIA GPU are required. Initial setup downloads dependencies and the approximately 8 GB base model. Run `EVALUATE-EVENTS.cmd` for the new development evaluation; stop the demo first to free GPU memory.

The submission limit is 120,000 characters and eight groups, including unassigned opening context. Each processed event retains its own 12,000-source-token limit. Put dates and other necessary context under the relevant heading. Grouping follows supplied labels; it does not establish which unlabeled incidents belong together.

Every draft needs human review. The model can still omit or misplace information, confuse attribution within an event, and suggest unsupported next steps. See the [2.5 validation record](reports/VALIDATION-V25.md) for measured results and the [roadmap](REVIEW-AND-ROADMAP.md) for remaining work. A clean install on another computer and representative-user validation remain outstanding. This is a synthetic-data proof of concept, with local inference and no hosted model endpoint.
