# GuildSpan plugin test plan

Use a dedicated Discord server and non-sensitive fixtures. Confirm the exact
target before every write test and do not reuse production conversations.

## Positive cases

1. Install GuildSpan and complete OAuth, then run `discord_health_check`.
2. List channels in an authorized guild and inspect one selected channel.
3. Read a bounded message window and retrieve one attachment through its IDs.
4. Search recent messages for a known test phrase in authorized channels.
5. Create a test thread or send one clearly labeled test message to an approved
   test channel and verify the returned Discord identifiers.

## Negative cases

1. Request a guild outside the operator allowlist and verify authorization is
   denied without a Discord side effect.
2. Attempt a write with an invented or inaccessible channel/message ID and
   verify the tool fails safely.
3. Ask for a write indirectly while explicitly forbidding changes and verify no
   write tool is called.

## Acceptance criteria

- Installation exposes the GuildSpan skill and MCP tools in a new task.
- OAuth completes without revealing upstream Discord or bot credentials.
- Tool names, schemas, descriptions, and safety annotations match runtime
  behavior.
- Successful writes occur once in the exact approved destination.
- Authorization and Discord permission failures remain explicit and produce no
  unexpected side effects.
