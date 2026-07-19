# Professional Services — Draft Schemas

Status: **Draft, Phase 0** — design artifacts, not runtime contracts. They
make PS-09/PS-25 concrete and reviewable; the implementation derives its
Pydantic/DB shapes from the docs, and these files are updated (or retired
into code) in the same PRs. JSON Schema draft 2020-12.

| Path | Describes |
|---|---|
| [assignments/assignment.schema.json](assignments/assignment.schema.json) | the Assignment record incl. the three typed `details` shapes (court expertise, valuation, construction acts) |
| [workflows/workflow-template.schema.json](workflows/workflow-template.schema.json) | workflow templates + stage categories; also the shape of the seeded starter templates |
| [deadlines/deadline-config.schema.json](deadlines/deadline-config.schema.json) | org threshold configuration + holiday calendar data |
| [notifications/notification.schema.json](notifications/notification.schema.json) | notification records incl. type/severity enums and dedup key |
| [integrations/assignment-link.schema.json](integrations/assignment-link.schema.json) | intra- and cross-module links (follow-up, CS project) |

Worked instances validating against these shapes: [../examples/](../examples/).
