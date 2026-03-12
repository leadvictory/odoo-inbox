
import imaplib
import re

IMAP_SERVER = "mail2.streamstorm.tv"
IMAP_PORT = 993
EMAIL = "info@performance-ag.ch"
PASSWORD = "0TXK$ZWQLkr9Kf9l"


# Detect encoded segments like &APw-
UTF7_PATTERN = re.compile(r'&[A-Za-z0-9+,]+-')


def decode_modified_utf7(name):
    """
    Decode IMAP modified UTF-7 parts inside a folder name
    """

    def repl(match):
        encoded = match.group(0)
        try:
            return imaplib.IMAP4._decode_utf7(encoded)
        except Exception:
            return encoded

    return UTF7_PATTERN.sub(repl, name)


def parse_folder(line):

    raw = line.decode(errors="ignore")

    parts = raw.split(' "/" ')

    if len(parts) < 2:
        return None, None

    name = parts[-1].replace('"', '')
    delimiter = "/"

    name = decode_modified_utf7(name)

    return name, delimiter


def build_tree(paths, delimiter):

    tree = {}

    for path in paths:

        parts = path.split(delimiter)
        node = tree

        for part in parts:
            node = node.setdefault(part, {})

    return tree


def print_tree(tree, indent=0):

    for name, children in sorted(tree.items()):
        print(" " * indent + name)
        print_tree(children, indent + 4)


def main():

    print("Connecting to IMAP server...\n")

    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL, PASSWORD)

    status, folders = mail.list()

    folder_names = []

    print("Decoded folders:\n")

    for f in folders:

        name, delimiter = parse_folder(f)

        if not name:
            continue

        folder_names.append(name)

        print(name)

    print("\nFolder Tree Structure:\n")

    tree = build_tree(folder_names, delimiter)

    print_tree(tree)

    mail.logout()


if __name__ == "__main__":
    main()