import argparse
import subprocess
import socket
import sys
import time
import json
import platform

VERSION = "1.0.0"

TARGETS = [
    "1.1.1.1",
    "8.8.8.8",
    "9.9.9.9",
    "77.88.8.8"
]

IP_HEADER = 20
ICMP_HEADER = 8
OVERHEAD = IP_HEADER + ICMP_HEADER


def resolve(host):
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def ping(host, mtu, timeout, count=1, df=True):
    payload = mtu - OVERHEAD

    if payload < 0:
        return False

    command = [
        "ping",
        "-4",
        "-n", str(count),
        "-w", str(int(timeout * 1000))
    ]

    if df:
        command.append("-f")

    command.extend(["-l", str(payload), host])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=(timeout * count) + 5
        )
        return result.returncode == 0

    except (subprocess.TimeoutExpired, OSError):
        return False


def test_mtu(host, mtu, timeout, retries):
    success = 0

    for _ in range(retries):
        if ping(host, mtu, timeout):
            success += 1

    required = (retries // 2) + 1
    return success >= required


def discover_mtu(host, minimum, maximum, timeout, retries):
    low = minimum
    high = maximum
    best = None

    print("\n[*] Testing:", host)

    if not test_mtu(host, minimum, timeout, retries):
        print("[FAILED] Minimum MTU test failed")
        return None

    best = minimum

    while low <= high:
        mid = (low + high) // 2

        print("[*] MTU %d ... " % mid, end="", flush=True)

        if test_mtu(host, mid, timeout, retries):
            best = mid
            low = mid + 1
            print("OK")
        else:
            high = mid - 1
            print("FAILED")

    return best


def packet_loss(host, timeout, count):
    success = 0

    for _ in range(count):
        if ping(host, 84, timeout, df=False):
            success += 1

    lost = count - success
    percentage = (lost / count) * 100

    return {
        "sent": count,
        "received": success,
        "lost": lost,
        "loss_percent": round(percentage, 2)
    }


def stability_test(host, timeout, count):
    print("\n[*] Stability Test:", host)

    result = packet_loss(host, timeout, count)

    print("    Sent:", result["sent"])
    print("    Received:", result["received"])
    print("    Lost:", result["lost"])
    print("    Packet Loss:", str(result["loss_percent"]) + "%")

    if result["loss_percent"] == 0:
        status = "EXCELLENT"
    elif result["loss_percent"] <= 5:
        status = "GOOD"
    elif result["loss_percent"] <= 15:
        status = "UNSTABLE"
    else:
        status = "POOR"

    print("    Stability:", status)
    result["status"] = status

    return result


def benchmark(hosts, detected, timeout, count, step):
    print("\n" + "=" * 55)
    print("             MTU BENCHMARK")
    print("=" * 55)

    candidates = []
    value = detected

    while value >= max(576, detected - 64):
        candidates.append(value)
        value -= step

    if detected not in candidates:
        candidates.insert(0, detected)

    results = []

    for mtu in candidates:
        total = 0
        success = 0

        print("\n[*] Testing MTU:", mtu)

        for host in hosts:
            for _ in range(count):
                total += 1

                if ping(host, mtu, timeout):
                    success += 1

        percentage = (success / total) * 100

        item = {
            "mtu": mtu,
            "sent": total,
            "successful": success,
            "success_percent": round(percentage, 2)
        }

        results.append(item)

        print("    Success:", success, "/", total)
        print("    Reliability:", str(round(percentage, 2)) + "%")

    stable = [
        item for item in results
        if item["success_percent"] >= 80
    ]

    best = max(stable, key=lambda item: item["mtu"]) if stable else None

    return results, best


def generate_config(mtu, filename):
    config = {
        "mtu": mtu
    }

    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)

        print("\n[OK] Xray/V2Ray MTU snippet saved:", filename)

    except OSError as error:
        print("[WARNING] Config generation failed:", error)


def main():
    parser = argparse.ArgumentParser(
        description="MTU Finder Pro 4.2.1"
    )

    parser.add_argument(
        "--targets",
        nargs="+",
        default=TARGETS,
        help="Hosts or IP addresses to test"
    )

    parser.add_argument(
        "--dns",
        nargs="+",
        default=None,
        metavar="IP",
        help="Test only these DNS server IP addresses"
    )

    parser.add_argument("--min", type=int, default=576)
    parser.add_argument("--max", type=int, default=1500)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--margin", type=int, default=8)

    parser.add_argument(
        "--benchmark-count",
        type=int,
        default=5
    )

    parser.add_argument(
        "--benchmark-step",
        type=int,
        default=8
    )

    parser.add_argument(
        "--stability-count",
        type=int,
        default=10
    )

    parser.add_argument(
        "--skip-benchmark",
        action="store_true"
    )

    parser.add_argument(
        "--skip-stability",
        action="store_true"
    )

    parser.add_argument(
        "--config",
        action="store_true"
    )

    args = parser.parse_args()

    if not 576 <= args.min < args.max <= 1500:
        parser.error("Invalid MTU range")

    if args.timeout <= 0:
        parser.error("Timeout must be positive")

    if not 1 <= args.retries <= 10:
        parser.error("Retries must be between 1 and 10")

    if not 0 <= args.margin < args.max:
        parser.error("Invalid safety margin")

    if not 1 <= args.benchmark_count <= 20:
        parser.error("Invalid benchmark count")

    if args.benchmark_step < 1:
        parser.error("Invalid benchmark step")

    if not 1 <= args.stability_count <= 100:
        parser.error("Invalid stability count")

    if platform.system() != "Windows":
        parser.error("This version currently supports Windows only")

    print("\n" + "=" * 55)
    print("             MTU FINDER PRO")
    print("                VERSION " + VERSION)
    print("=" * 55)

    print("Operating System:", platform.system())
    print("Mode: Normal Internet")
    print("VPN Required: NO")
    print("TUN Required: NO")
    print("External Libraries: NONE")

    print("\n[*] Starting Network Analysis...")

    results = []

    # با --dns فقط همان IPهای واردشده تست می‌شوند.
    # بدون --dns، مقصدهای --targets (یا مقصدهای پیش‌فرض) تست می‌شوند.
    targets = args.dns if args.dns is not None else args.targets

    # حذف مقصدهای تکراری، با حفظ ترتیب
    targets = list(dict.fromkeys(targets))

    for target in targets:
        ip = resolve(target)

        if not ip:
            print("[SKIP] DNS failed:", target)
            continue

        mtu = discover_mtu(
            ip,
            args.min,
            args.max,
            args.timeout,
            args.retries
        )

        if mtu is not None:
            results.append({
                "host": target,
                "ip": ip,
                "path_mtu": mtu,
                "limit_reached": mtu == args.max
            })

            print("[SUCCESS]", target, ":", mtu)

    if not results:
        print("\n[ERROR] No successful MTU tests.")
        print("Check internet connection and ICMP firewall.")
        return 2

    detected = min(item["path_mtu"] for item in results)
    suggested = max(576, detected - args.margin)

    stability_results = []

    if not args.skip_stability:
        print("\n" + "=" * 55)
        print("             NETWORK STABILITY")
        print("=" * 55)

        for item in results:
            stability = stability_test(
                item["ip"],
                args.timeout,
                args.stability_count
            )

            stability["host"] = item["host"]
            stability_results.append(stability)

    benchmark_results = []
    benchmark_best = None

    if not args.skip_benchmark:
        hosts = [item["ip"] for item in results]

        benchmark_results, benchmark_best = benchmark(
            hosts,
            detected,
            args.timeout,
            args.benchmark_count,
            args.benchmark_step
        )

        if benchmark_best:
            print("\n[BENCHMARK WINNER]", benchmark_best["mtu"])

            suggested = max(
                576,
                min(
                    suggested,
                    benchmark_best["mtu"] - args.margin
                )
            )

    print("\n" + "=" * 55)
    print("             FINAL RESULTS")
    print("=" * 55)

    for item in results:
        status = (
            "LIMIT REACHED"
            if item["limit_reached"]
            else "DETECTED"
        )

        print(
            "%-15s %4d bytes [%s]" %
            (
                item["host"],
                item["path_mtu"],
                status
            )
        )

    print("\nDetected Conservative Path MTU:", detected)

    print("\n" + "*" * 55)
    print("          RECOMMENDED V2RAY MTU")
    print("*" * 55)

    print("\n                  %d" % suggested)

    print("\nSuggested for:")
    print("- v2rayN")
    print("- PattNG")
    print("- v2rayNG")
    print("- v2rayTun")
    print("- Xray TUN")

    print("\n[INFO] This is a normal internet estimate.")
    print("[INFO] VPN and TUN are not required.")
    print("[INFO] VPN tunnel overhead is not measured.")

    if args.config:
        generate_config(
            suggested,
            "v2ray_mtu_config.json"
        )

    report = {
        "version": VERSION,
        "operating_system": platform.platform(),
        "mode": "Normal IPv4 Internet",
        "vpn_required": False,
        "tun_required": False,
        "tested_targets": targets,
        "detected_path_mtu": detected,
        "safety_margin": args.margin,
        "recommended_v2ray_mtu": suggested,
        "mtu_results": results,
        "stability_results": stability_results,
        "benchmark_results": benchmark_results,
        "benchmark_best": benchmark_best,
        "settings_changed": False
    }

    try:
        with open(
            "mtu_result.json",
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                report,
                file,
                indent=4,
                ensure_ascii=False
            )

        print("\n[OK] Report saved: mtu_result.json")

    except OSError as error:
        print("\n[WARNING] Cannot save report:", error)

    print("\n" + "=" * 55)
    print("          MTU FINDER PRO FINISHED")
    print("=" * 55)

    return 0


if __name__ == "__main__":
    start = time.time()

    try:
        code = main()

    except KeyboardInterrupt:
        print("\n[STOPPED] Test cancelled.")
        code = 130

    print(
        "\nFinished in %.2f seconds." %
        (time.time() - start)
    )

    sys.exit(code)
