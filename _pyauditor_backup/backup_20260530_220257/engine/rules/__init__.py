from engine.rules.async_rules import AsyncioLockRaceRule, BlockingInAsyncRule, MissingAwaitRule
from engine.rules.safety_rules import (BareExceptRule, ExceptPassRule, MutableDefaultArgRule,
                                        ShadowBuiltinRule, OsExitRule)
from engine.rules.dead_code import (DeadParameterRule, UnusedSelfAttrRule, WidgetNotPackedRule,
                                     DuplicateListItemsRule, UnusedImportRule)
from engine.rules.design import (LongFunctionRule, DeepNestingRule, MissingTypeHintRule,
                                   MissingDocstringRule, LongLineRule)
from engine.rules.potential import (MagicNumberRule, TodoFixmeRule, HardcodedPathRule,
                                     PrintStatementRule, BroadExceptionCatchRule,
                                     MultiwordStopwordRule, StaleLogValueRule)

ALL_RULES = [
    # CRITICAL — Async
    AsyncioLockRaceRule(),
    BlockingInAsyncRule(),
    MissingAwaitRule(),
    # WARNING — Safety
    BareExceptRule(),
    ExceptPassRule(),
    MutableDefaultArgRule(),
    ShadowBuiltinRule(),
    OsExitRule(),
    # WARNING — Dead Code
    DeadParameterRule(),
    UnusedSelfAttrRule(),
    WidgetNotPackedRule(),
    DuplicateListItemsRule(),
    # POTENTIAL
    MagicNumberRule(),
    TodoFixmeRule(),
    HardcodedPathRule(),
    PrintStatementRule(),
    BroadExceptionCatchRule(),
    MultiwordStopwordRule(),
    StaleLogValueRule(),
    # INFO — Design
    LongFunctionRule(),
    DeepNestingRule(),
    MissingTypeHintRule(),
    MissingDocstringRule(),
    LongLineRule(),
    # INFO — Dead Code
    UnusedImportRule(),
]

RULE_MAP = {r.rule_id: r for r in ALL_RULES}

CATEGORIES = sorted(set(r.category for r in ALL_RULES))
