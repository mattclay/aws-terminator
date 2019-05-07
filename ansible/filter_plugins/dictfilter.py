# Copyright (C) 2016 Matt Clay <matt@mystile.com>
# GNU General Public License v3.0+ (see ansible/LICENSE.md or https://www.gnu.org/licenses/gpl-3.0.txt)


def dictfilter(item, keys):
    return {k: item[k] for k in item if k in keys}


class FilterModule(object):
    def filters(self):
        return dict(
            dictfilter=dictfilter,
        )
