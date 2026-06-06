import argparse
import sys
from protocol import DISPLAY_MODE
from sender import run_sender
from receiver import Receiver


def main():
    parser = argparse.ArgumentParser(
        description="QR File Transfer — send files between PCs using QR codes"
    )
    parser.add_argument(
        "role",
        choices=["sender", "receiver"],
        help="Run as sender (transmit) or receiver (receive)",
    )
    parser.add_argument(
        "--source",
        help="Source directory to send (required for sender)",
    )
    parser.add_argument(
        "--dest",
        default="./received",
        help="Destination directory (default: ./received)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last saved state",
    )
    parser.add_argument(
        "--display",
        choices=["image", "ascii"],
        help=f"QR display mode (default: {DISPLAY_MODE})",
    )

    args = parser.parse_args()

    if args.role == "sender":
        if not args.source:
            print("Error: --source is required for sender")
            sys.exit(1)
        run_sender(args.source, resume=args.resume, display_mode=args.display)
    else:
        recv = Receiver(args.dest, display_mode=args.display)
        recv.run(resume=args.resume)


if __name__ == "__main__":
    main()
