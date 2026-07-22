              Runtime Orchestrator
                     │
 ┌───────────────────┼────────────────────┐
 ▼                   ▼                    ▼
Session          Pipeline             Commands
 │                   │                    │
 └────────────┬──────┴──────────────┬─────┘
              ▼                     ▼
        Execution Engine      Runtime Events
              │                     ▲
              ▼                     │
         Runtime Entities───────────┘