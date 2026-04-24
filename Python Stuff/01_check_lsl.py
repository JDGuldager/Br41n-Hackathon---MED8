from pylsl import resolve_streams

print("Searching for all LSL streams...")
streams = resolve_streams(wait_time=10)

if not streams:
    print("No LSL streams found.")
else:
    for i, s in enumerate(streams):
        print(f"\nStream {i}")
        print("Name:", s.name())
        print("Type:", s.type())
        print("Channels:", s.channel_count())
        print("Rate:", s.nominal_srate())
        print("Source ID:", s.source_id())