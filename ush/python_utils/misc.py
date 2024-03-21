#!/usr/bin/env python3

import re


def uppercase(s):
    """Function to convert a given string to uppercase

    Args:
        s: the string
    Return:
        Uppercased str
    """

    return s.upper()


def lowercase(s):
    """Function to convert a given string to lowercase

    Args:
        s: the string
    Return:
        Lowercase str
    """

    return s.lower()


def find_pattern_in_str(pattern, source):
    """Find regex pattern in a string

    Args:
        pattern: regex expression
        source: string
    Return:
        A tuple of matched groups or None
    """
    pattern = re.compile(pattern)
    for match in re.finditer(pattern, source):
        return match.groups()
    return None


def find_pattern_in_file(pattern, file_name):
    """Find regex pattern in a file

    Args:
        pattern: regex expression
        file_name: name of text file
    Return:
        A tuple of matched groups or None
    """
    pattern = re.compile(pattern)
    with open(file_name) as f:
        for line in f:
            for match in re.finditer(pattern, line):
                return match.groups()
    return None


def dict_find(user_dict, substring):
    """Find any keys in a dictionary that contain the provided substring

    Args:
        user_dict: dictionary to search
        substring: substring to search keys for
    Return:
        True if substring found, otherwise False
    """

    if not isinstance(user_dict, dict):
        return False

    for key, value in user_dict.items():
        if substring in key:
            return True
        if isinstance(value, dict):
            if dict_find(value, substring):
                return True

    return False

