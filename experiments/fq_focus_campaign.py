"""Separate structural search configuration for three high-impact families.

The generic multiscale runtime snapshots these explicit weights and mode slots;
no already-running campaign is altered by importing it in this new process.
"""
import fq_multiscale_campaign as campaign

campaign.FOCUS = {'5_17_7': 3, '17_5_7': 3,
                  '7_19_13': 2, '19_7_13': 2,
                  '7_20_14': 2, '20_7_14': 2}
campaign.MODE_SLOTS = ['kick_030', 'kick_010', 'rounded', 'kick_080',
                       'kick_030', 'rounded', 'kick_003', 'kick_010']

if __name__ == '__main__':
    campaign.main()
