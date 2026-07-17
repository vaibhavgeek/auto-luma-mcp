# Five-Minute Judge Demo

## Primary Fixture Sequence

1. Start the local topology:

   ```sh
   make demo-up
   ```

2. Seed a rehearsal artifact:

   ```sh
   make demo-seed
   ```

3. Run the fixture workflow:

   ```sh
   make demo-run
   ```

4. In the MCP client, describe the live-equivalent flow:

   - Connect to Nexla's MCP endpoint. In fixture mode this is `fake-nexla`; in live mode it is `NEXLA_MCP_ENDPOINT`.
   - Call `login`.
   - Enter email `demo@lumabot.local`.
   - Enter verification code `000000` for fixture mode.
   - Call `set_user_profile` with:

     ```text
     I am looking for engineering roles at seed-stage AI or developer-tool companies with fewer than 50 employees. I want to meet founders, engineering leaders and hiring managers at Bay Area hackathons.
     ```

   - Call `recommend_events`.
   - Select `Bay Area AI Hacknight`.
   - Call `get_job_status` until the job is complete.
   - Call `get_event_report`.

5. Show the report fields:

   - Top people: Avery Chen, Mina Patel, Jordan Rivera.
   - Company stages: seed and series-a in the fixture data.
   - Relevance scores: founder, engineering, and hiring-manager roles rank highest.
   - Identity-confidence scores: fake Nexla confidence values are persisted per attendee.
   - AgentMail delivery: the report includes `message_id` and `thread_id`.
   - Zero artifact: the report links a Networking Bingo page.

6. Explain the architecture:

   - Nexla enriches attendees through a Streamable HTTP MCP endpoint.
   - Akash hosts the public MCP endpoint, runtime API, private worker, and singleton scheduler.
   - Supabase or PostgreSQL persists users, jobs, attendees, enrichments, reports, delivery IDs, and Zero page IDs.
   - MCP tools provide login, profile, event recommendation, job polling, and report retrieval.
   - Background runtime jobs do browser scraping, enrichment, scoring, delivery, and artifact creation.

7. Stop the topology:

   ```sh
   make demo-down
   ```

## Fixture-Only Fallback

If sponsor services or Akash are unavailable, run:

```sh
make integration-test
make demo-run
```

This exercises the same production-facing contracts with fake Nexla, fake AgentMail, fake Zero, and an in-memory fixture runtime. The output proves idempotent replay: repeated runs do not duplicate attendees, jobs, reports, email sends, event registration, or Zero pages.
