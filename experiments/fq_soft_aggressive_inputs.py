"""Add certified neighboring-count families to the fair soft-search reference."""
import argparse
from pathlib import Path
import sys

import fq_soft_inputs as soft_inputs
from fq_variant_campaign import load_poses


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--add-family-source', type=Path, action='append', required=True)
    args, remainder = parser.parse_known_args()
    inputs = soft_inputs.inputs
    for path in args.add_family_source:
        for key in load_poses(path):
            inputs.FAMILIES.add(inputs.family(key))
        remainder += ['--source', str(path)]
    sys.argv = [sys.argv[0], *remainder]
    inputs.main()


if __name__ == '__main__':
    main()
