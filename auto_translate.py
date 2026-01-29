import xml.etree.ElementTree as ET
import os
import argparse
from google.cloud import translate_v3


def auto_translate(
    ts_file, target_lang, output_file=None, batch_size=50, project_id=None
):
    if not project_id:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("Error: GOOGLE_CLOUD_PROJECT environment variable not set.")
    if not os.path.exists(ts_file):
        print(f"Error: {ts_file} not found.")
        return

    if output_file is None:
        output_file = ts_file

    try:
        # Parse XML
        tree = ET.parse(ts_file)
        root = tree.getroot()

        # Determine language code from file name if not provided
        if not target_lang:
            filename = os.path.basename(ts_file)
            if filename.endswith(".ts"):
                target_lang = filename[:-3]
                print(f"Detected language code from filename: {target_lang}")

        # Fallback to TS language attribute
        if not target_lang:
            target_lang = root.attrib.get("language")
            if target_lang:
                # TS usually uses xx_YY, Google wants xx
                target_lang = target_lang.split("_")[0]
                print(f"Detected language code from TS attribute: {target_lang}")
            else:
                print(
                    "Error: Target language not specified and not found in .ts file or filename."
                )
                return

        messages = root.findall(".//message")
        print(
            f"Found {len(messages)} messages in {ts_file}. Target language: {target_lang}"
        )

        # Extract sources for messages that need translation
        to_translate = []  # List of (index, text)
        for i, message in enumerate(messages):
            source = message.find("source")
            translation_tag = message.find("translation")

            # Check if translation exists and is not empty
            has_translation = (
                translation_tag is not None
                and translation_tag.text
                and translation_tag.text.strip()
            )

            # Also check for "unfinished" type which usually means it needs translation
            is_unfinished = (
                translation_tag is not None
                and translation_tag.attrib.get("type") == "unfinished"
            )

            if (
                (not has_translation or is_unfinished)
                and source is not None
                and source.text
            ):
                text = source.text.replace("\n", " ")
                to_translate.append((i, text))

        if not to_translate:
            print("No messages need translation.")
            return

        print(f"Translating {len(to_translate)} new/unfinished messages...")

        # Translate in batches
        translated_map = {}  # Map original index to translated text
        client = translate_v3.TranslationServiceClient()

        sources_to_batch = [item[1] for item in to_translate]
        indices_to_batch = [item[0] for item in to_translate]

        for i in range(0, len(sources_to_batch), batch_size):
            batch = sources_to_batch[i : i + batch_size]
            batch_indices = indices_to_batch[i : i + batch_size]

            print(f"Translating batch {i//batch_size + 1} ({len(batch)} strings)...")

            request = translate_v3.TranslateTextRequest(
                contents=batch,
                parent=project_id,
                target_language_code=target_lang,
            )

            resp = client.translate_text(request=request)
            for idx, translation in zip(batch_indices, resp.translations):
                translated_map[idx] = translation.translated_text

        # Apply translations
        for i, message in enumerate(messages):
            if i in translated_map:
                translation_tag = message.find("translation")
                if translation_tag is None:
                    translation_tag = ET.SubElement(message, "translation")

                translation_tag.text = translated_map[i]
                # Remove type="unfinished" if it exists
                if "type" in translation_tag.attrib:
                    del translation_tag.attrib["type"]

        # Save the updated XML
        with open(output_file, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write(b"<!DOCTYPE TS>\n")
            ET.indent(tree, space="    ", level=0)
            tree.write(f, encoding="utf-8", xml_declaration=False)

        print(
            f"Successfully applied {len(translated_map)} translations to {output_file}"
        )

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automatically translate .ts files using Google Translate API."
    )
    parser.add_argument("input", help="Input .ts file")
    parser.add_argument(
        "--lang",
        help="Target language code (e.g., 'ja', 'de'). If omitted, will try to detect from .ts file.",
    )
    parser.add_argument(
        "--output", help="Output .ts file (defaults to overwriting input)"
    )
    parser.add_argument(
        "--batch", type=int, default=50, help="Batch size for API calls (default: 50)"
    )
    parser.add_argument(
        "--project_id", help="Google Cloud project ID for authentication"
    )

    args = parser.parse_args()

    auto_translate(args.input, args.lang, args.output, args.batch, args.project_id)
