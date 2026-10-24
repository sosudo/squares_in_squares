"""Orientation-fair inputs for structural soft-square continuation."""
import fq_focus_inputs as inputs

# Three full-score bottleneck families, the new capacity-relevant family,
# and every multiscale winner whose excess reduction exceeded 1e-5.
inputs.FAMILIES = {
    (5, 17, 7), (7, 19, 13), (7, 20, 14), (6, 22, 16),
    (8, 22, 14), (8, 20, 12), (8, 21, 8),
    (10, 23, 17), (9, 20, 12), (10, 23, 14),
}

if __name__ == '__main__':
    inputs.main()
