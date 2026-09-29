# Pytest prompt template

Used this skeleton to make ai results more consistant across usage
Would fill out the sections that are specific to each test and then leave the rest of skeleton to save 
rewriting.

```text
Write one pytest [unit/integration] test for [FUNCTION OR BEHAVIOUR].

The test must verify that [PRECISE BEHAVIOURAL REQUIREMENT].

Structure the test using Arrange-Act-Assert:
- Arrange: [INPUTS, FIXTURES, CONFIGURATION, PATCHES, OR INITIAL STATE].
- Act: [EXACT FUNCTION OR OPERATION TO CALL].
- Assert: [EXPECTED RETURN VALUE, EXCEPTION, CALL, STATE, OR SIDE EFFECT].

[Use pytest.mark.parametrize for CASES and provide descriptive case IDs.]
[Use the existing FIXTURE/HELPER rather than duplicating its setup.]
[Patch DEPENDENCY at the location where the module under test imports it.]

Test-writing constraints:
- Keep the test deterministic by using fixed timestamps and values.
- Do not use real sleeps when testing timing or retry behaviour.
- Assert observable behaviour rather than implementation details, except where
  an exact command or collaborator call is part of the contract.
- Use clear test and case names and follow the existing test style.
```

Not every prompt needs every constraint. Pure functions normally need no mocks;
boundary adapters normally need patched collaborators; integration tests should
state their external prerequisites explicitly.
