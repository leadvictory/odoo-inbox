import re
import base64
import imaplib


class IMAPHelper:

    IMAP_LIST_RE = re.compile(
        r'^\((?P<flags>.*?)\)\s+"(?P<delim>.*?)"\s+(?P<name>.+)$'
    )

    def __init__(self, imap_conn):
        self.imap = imap_conn
        self.folders = []
        self._load_folders()

    # ---------------------------------------------------
    # Decode IMAP UTF7
    # ---------------------------------------------------

    def decode_utf7(self, s):

        def repl(match):
            b64 = match.group(1)

            if b64 == "":
                return "&"

            b64 = b64.replace(",", "/")
            pad = "=" * (-len(b64) % 4)

            return base64.b64decode(b64 + pad).decode("utf-16-be")

        return re.sub(r"&([A-Za-z0-9+,]*)-", repl, s)

    # ---------------------------------------------------
    # Load folders
    # ---------------------------------------------------

    def _load_folders(self):

        status, folders = self.imap.list()

        if status != "OK":
            return

        parsed = []

        for f in folders:

            raw = f.decode(errors="ignore")

            m = self.IMAP_LIST_RE.match(raw)

            if not m:
                continue

            name = m.group("name").strip()

            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]

            name = self.decode_utf7(name)

            parsed.append(name)

        # remove duplicates
        self.folders = sorted(set(parsed))

    # ---------------------------------------------------
    # Detect special folders
    # ---------------------------------------------------

    def get_trash_folder(self):

        for f in self.folders:

            name = f.lower()

            if any(x in name for x in [
                "trash",
                "deleted",
                "gelöscht",
                "geloscht",
                "bin"
            ]):
                return f

        return None

    def get_sent_folder(self):

        for f in self.folders:

            name = f.lower()

            if any(x in name for x in [
                "sent",
                "gesendet",
                "sent items"
            ]):
                return f

        return None

    def get_drafts_folder(self):

        for f in self.folders:

            name = f.lower()

            if "draft" in name:
                return f

        return None

    # ---------------------------------------------------
    # Find message across folders
    # ---------------------------------------------------

    def find_message(self, message_id):

        for folder in self.folders:

            try:
                status, _ = self.imap.select(f'"{folder}"')
            except imaplib.IMAP4.error:
                continue

            if status != "OK":
                continue

            status, data = self.imap.search(
                None,
                f'(HEADER Message-ID "{message_id}")'
            )

            if data and data[0]:

                return folder, data[0].split()

        return None, None

    # ---------------------------------------------------
    # Move message
    # ---------------------------------------------------

    def move_to_folder(self, msg_num, source_folder, dest_folder):

        self.imap.select(f'"{source_folder}"')

        self.imap.copy(msg_num, f'"{dest_folder}"')

        self.imap.store(msg_num, '+FLAGS', '\\Deleted')

        self.imap.expunge()