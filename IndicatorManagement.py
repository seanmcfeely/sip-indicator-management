#!/usr/bin/env python3

import os
import argparse
import coloredlogs
import datetime
import logging
import sys
import json

from indicator_management import IndicatorManager

os.environ['NO_PROXY'] = '.local'

LOGGER = logging.getLogger('indicator_management')

def reset_in_progress(args):
    im = IndicatorManager(dev=args.dev)
    im.reset_in_progress()

def turn_off_indicators(args):
    im = IndicatorManager(dev=args.dev)
    im.turn_off_indicators_according_to_tune_instructions(dry_run=args.dry_run)

def build_parser(parser: argparse.ArgumentParser):
    """Build the CLI Argument parser."""

    parser.add_argument("-d", "--debug", default=False, action="store_true", help="Turn on debug logging.")

    parser.add_argument('--dev', action='store_true', dest='dev', required=False, default=False,
        help='Interact with dev SIP instead of production.')

    subparsers = parser.add_subparsers(dest='cmd', help='Various commands for the Indicator Manager')

    reset_in_progress_parser = subparsers.add_parser('reset_in_progress', help='Reset In Progress indicators to New.')
    reset_in_progress_parser.set_defaults(func=reset_in_progress)

    find_fp_recon_parser = subparsers.add_parser('tune_intel', help='Find all Analyzed indicators matching tuning configurations and turn them off.')
    find_fp_recon_parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run', required=False, default=False,
                                     help='Flag to not disable the indicators found.')
    find_fp_recon_parser.set_defaults(func=turn_off_indicators)

    return True


def main(args=None):
    """The main CLI entry point."""

    # configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)s] %(message)s")
    coloredlogs.install(level="INFO", logger=LOGGER)

    if not args:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="SIP indicator management for ACE ecosystems.")
    build_parser(parser)
    args = parser.parse_args(args)

    if args.debug:
        coloredlogs.install(level="DEBUG", logger=LOGGER)
    
    args.func(args)

    return True


if __name__ == '__main__':
    sys.exit(main())