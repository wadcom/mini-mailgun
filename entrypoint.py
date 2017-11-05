#! /usr/bin/env python3

import argparse
import subprocess

MODES = {
    'frontend': ['/app/frontend.py'],
    'unittests': ['python3', '-m', 'unittest',
        'frontend',
        'mailqueue'
    ]
}

def main():
    args = parse_arguments()

    if args.mode not in MODES:
        raise NotImplementedError

    subprocess.run(MODES[args.mode], check=True)


def parse_arguments():
    parser = argparse.ArgumentParser(description='MiniMailGun entrypoint')
    parser.add_argument('mode', help='mode to start in', choices=sorted(MODES.keys()))

    return parser.parse_args()


if __name__ == '__main__':
    main()