#! /usr/bin/env python3

import argparse
import subprocess

def main():
    args = parse_arguments()

    if args.mode == 'frontend':
        subprocess.run(['/app/frontend.py'], check=True)
    elif args.mode == 'unittests':
        modules = [
            'frontend'
        ]
        subprocess.run(['python3', '-m', 'unittest'] + modules, check=True)
    else:
        raise NotImplementedError


def parse_arguments():
    parser = argparse.ArgumentParser(description='MiniMailGun entrypoint')
    parser.add_argument('mode', help='mode to start in', choices=['frontend', 'unittests'])

    return parser.parse_args()


if __name__ == '__main__':
    main()