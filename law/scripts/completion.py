# -*- coding: utf-8 -*-

"""
"law completion" command line tool
"""


from law.util import law_base


def setup_parser(sub_parsers):
    sub_parsers.add_parser("completion", prog="law completion",
        description="law completion file lookup")


def execute(args):
    print(law_base("completion.sh"))
