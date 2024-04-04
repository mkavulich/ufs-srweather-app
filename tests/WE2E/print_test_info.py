#!/usr/bin/env python3

import argparse
import sys

sys.path.append("../../ush")

from python_utils import print_test_info

if __name__ == "__main__":

    #Parse arguments
    parser = argparse.ArgumentParser(
                     description="Script for parsing all test files in the test_configs/ "\
                     "directory, and printing a pipe-delimited summary file of the details of "\
                     "each test.\n")

    parser.add_argument('-o', '--output_file', type=str,
                        help='File name for test details file', default='')

    args = parser.parse_args()

    if args.output_file:
        print_test_info(args.output_file)
    else:
        print_test_info()
