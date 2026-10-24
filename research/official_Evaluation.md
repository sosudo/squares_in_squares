## Scoring Formula

**Lower is better.** For each puzzle \\(n\\), your score is the *excess* of your achieved container side length \\(L\\) over the area-based lower bound:

    score(n) = L / √n − 1

The leaderboard is the sum of all puzzles. See the competition metric [notebook](https://www.kaggle.com/code/metric/squares-in-squares) for details.

## Submission File
The submission file requires a unique integer `id` column. **Partial submissions are allowed.** You don't need to submit solutions for all 1,000 puzzles; a missing puzzle scores \\(L\_0 / \sqrt{n} - 1\\), the same as the trivial grid packing for that n.

Coordinates must be plain decimal literals, optionally in scientific notation. A puzzle whose coordinates do not parse is charged the grid ceiling. The container side length L is not submitted; it is computed from your squares.

    id,n,square_id,x,y,angle
    0,1,0,0.5,0.5,0
    1,2,0,0.5,0.5,0
    2,2,1,1.5,0.5,0
    3,3,0,0.5,0.5,0
    etc.