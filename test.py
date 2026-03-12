from imapclient import IMAPClient

IMAP_SERVER = "mail2.streamstorm.tv"
IMAP_PORT = 993

EMAIL = "info@performance-ag.ch"
PASSWORD = "0TXK$ZWQLkr9Kf9l"


def build_tree(paths):
    tree = {}

    for path in paths:
        parts = path.split("/")
        current = tree

        for part in parts:
            current = current.setdefault(part, {})

    return tree


def print_tree(tree, indent=0):
    for key, value in sorted(tree.items()):
        print("  " * indent + key)
        print_tree(value, indent + 1)


def main():
    with IMAPClient(IMAP_SERVER, port=IMAP_PORT, ssl=True) as server:
        server.login(EMAIL, PASSWORD)

        folders = server.list_folders()

        folder_paths = [folder[2] for folder in folders]

        tree = build_tree(folder_paths)

        print("\nMailbox Folder Structure:\n")
        print_tree(tree)


if __name__ == "__main__":
    main()