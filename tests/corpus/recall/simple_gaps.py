"""Recall fixture: simple node-local rules.

`long_report` exceeds 50 lines and SHOULD be caught by LongFunctionDetector
(regression guard — this one is expected to HIT).

`copy_items` is a no-op list comprehension (`[x for x in xs]`) — pure waste.
There is no UselessListComp detector yet, so it is expected to MISS until one
is added. The label documents the gap.
"""


def copy_items(xs):
    dup = [x for x in xs]  # EXPECT: UselessListComp
    return dup


def long_report(data):  # EXPECT: LongFunction
    line_01 = data
    line_02 = data
    line_03 = data
    line_04 = data
    line_05 = data
    line_06 = data
    line_07 = data
    line_08 = data
    line_09 = data
    line_10 = data
    line_11 = data
    line_12 = data
    line_13 = data
    line_14 = data
    line_15 = data
    line_16 = data
    line_17 = data
    line_18 = data
    line_19 = data
    line_20 = data
    line_21 = data
    line_22 = data
    line_23 = data
    line_24 = data
    line_25 = data
    line_26 = data
    line_27 = data
    line_28 = data
    line_29 = data
    line_30 = data
    line_31 = data
    line_32 = data
    line_33 = data
    line_34 = data
    line_35 = data
    line_36 = data
    line_37 = data
    line_38 = data
    line_39 = data
    line_40 = data
    line_41 = data
    line_42 = data
    line_43 = data
    line_44 = data
    line_45 = data
    line_46 = data
    line_47 = data
    line_48 = data
    line_49 = data
    line_50 = data
    line_51 = data
    line_52 = data
    return line_52
