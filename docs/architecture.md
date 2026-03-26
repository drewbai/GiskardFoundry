# GiskardFoundry Architecture

```mermaid
flowchart TB
  subgraph EntryLayer[Entry Layer]
    CLI[giskardfoundry-server\nCLI Entrypoint]
    HTTP[MAF HTTP Hosting Adapter]
  end

  subgraph OrchestrationLayer[Orchestration Layer]
    SC[SusanCalvin]
    OA[OrchestratorAgent]
  end

  subgraph DomainLayer[Domain Agent Layer]
    ON[OneNoteAgent]
    GTD[GTDAgent]
    JOB[JobSearchAgent]
    EX[ExampleAgent]
  end

  subgraph ToolingLayer[Tooling Layer]
    REG[Tool Registry]
    BASE[BaseTool]
    TOOLS[Concrete Tools]
  end

  subgraph ConfigLayer[Configuration Layer]
    MAN[Agent Manifests]
    SCH[Manifest Schema]
    CFG[Framework + Settings Config]
    ENV[Runtime Environment Variables]
  end

  subgraph ExternalBoundary[External Boundary]
    FDY[Foundry Runtime APIs]
    ID[Identity + Credentials]
  end

  CLI --> SC
  HTTP --> SC
  SC --> OA
  OA --> ON
  OA --> GTD
  OA --> JOB
  OA --> EX

  ON --> REG
  GTD --> REG
  JOB --> REG
  EX --> REG

  REG --> BASE
  REG --> TOOLS

  OA --> MAN
  OA --> SCH
  SC --> CFG
  HTTP --> ENV

  HTTP --> FDY
  HTTP --> ID
```

## Notes

- Scope emphasizes portfolio-safe architecture and public framework boundaries.
- Competitive logic and private evaluation rules are intentionally excluded from this view.
