from subprocess import run
from sys import argv
import re 
import logging
log = logging.getLogger(__name__)
logging.basicConfig()

# Crawl files in the given directory and return a set of matched Youtube ID 
# from their filenames.

cmd = [
        "find", argv[1], 
        # "-type", "f", r"\(", "-iname", "'*.mkv'", "-o", "-iname", "'*.mp4'", "-printf", r"\)", r"%f\n", 
        "-type", "f", 
        "-iregex", r'.*\.\(mkv\|mp4\|opus\|m4a\|webm\)', "-printf", r"%f\n",
        # "|", "sed", "-n", r's/^.*\][\s_]\?\(.*\)\..\{3,4\}$/\1/p'
    ]

print(f"cmd: {cmd}")

proc = run(
    cmd,
    # shell=True,
    check=False,
    capture_output=True, # stdout=DEVNULL, stderr=DEVNULL
    # stdout=PIPE,
    text=True
)

youtube_id_re = re.compile(r'.*[\s_]?([0-9A-Za-z_-]{11})\..{3,4}$', re.IGNORECASE)

def find_youtube_id(file_list: list):
    ids = []  # a list, not a set to keep the order resulting from the file list
    miss = []
    dupes = []
    for fname in file_list:
        match = youtube_id_re.match(fname)
        if match:
            group = match.group(1)
            if group in ids:
                log.warning(f"ID \'{group}\' from \'{fname}\' was already found.")
                dupes.append(fname)
            else:   
                ids.append(group)
        else:
            log.info(f"Did not match regex: {fname}")
            miss.append(fname)
    return ids, miss, dupes


def sort_output(output: str):
    line_count = 0
    filenames = []
    for line in output.split('\n'):
        line = line.rstrip()
        if len(line) > 0:
            line_count += 1
            filenames.append(line)
    filenames.sort()
    for fname in filenames:
        log.debug(fname)
    return filenames, line_count


filenames, count = sort_output(proc.stdout)
print(f"Total files found by suffix: {count}")

ids, misses, dupes = find_youtube_id(filenames)
print(f"IDs found (most ancient at the top):")

with open("ids_found.txt", "w") as f:
    for _id in ids:  # reversed: ids[::-1]:
        print(_id)
        f.write(_id + '\n')
print(f"Total found: {len(ids)}.")

print(f"{len(misses)} mismatched files + {len(dupes)} dupes = {len(misses) + len(dupes)}:")
for miss in misses:
    print(miss)