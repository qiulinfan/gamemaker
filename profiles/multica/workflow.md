# Multica adapter

Use this profile only when the user explicitly selects Multica and an already
configured client is available. The portable workflow remains authoritative for
scope, ownership, evidence, and acceptance.

## Resolve before dispatch

Inspect live state once at the start of the producer run:

- resolve the intended workspace, agent, and online runtime by exact IDs;
- search for an existing active child with the same parent and deliverable;
- verify the child will write to the production workflow's canonical workspace,
  not an isolated runtime work directory;
- inherit the parent external-effect and source-control policy.

Do not install a client, deploy a server, create a workspace, or start a
persistent service merely because the adapter was selected. Use the dedicated
Multica setup or runtime workflow only when the user separately authorizes it.

## Create one ready stage

Translate the portable handoff contract into one issue containing:

1. parent ID and slice route;
2. one owned deliverable;
3. authoritative inputs and exact paths;
4. scope and non-goals;
5. write boundaries and blockers;
6. selected Skills;
7. acceptance checks and evidence;
8. canonical workspace verification;
9. inherited external-effect policy;
10. next owner and expected artifact.

Resolve exact agent and runtime IDs. Create the child once. Do not pre-create
future dependency stages or duplicate a failed dispatch until live state proves
that no issue/run exists.

## Use event-driven handoffs

Each child publishes its evidence and marks its own issue `done`. In this
adapter, child `done` means that specialist output is ready for producer
review; it does not accept the parent slice.

Record child issue ID, task/run ID, and observed message cursor. End the producer
run after dispatch. Let the completion event or mention trigger the next run.
On wake, deduplicate recorded IDs before integrating.

Do not keep a shell loop, sleep, repeated issue query, or repository poll alive.
For explicit operational recovery only, perform one bounded observation and
advance the stored cursor; do not reread complete history.

The producer must inspect the actual artifact, route defects through the
portable workflow, and close the parent only after independent acceptance.
