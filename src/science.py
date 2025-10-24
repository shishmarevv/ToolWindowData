"""
Module for statistical analysis of episode duration data.

Purpose: Compare duration of tool window sessions between manual and auto opening.
"""

import sqlite3
import statistics
from pathlib import Path
from collections import defaultdict
import io
import base64
from . import resolver

# For statistical tests we use scipy
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not installed. Statistical tests will be unavailable.")

# For plotting we use matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # Use backend without GUI for web
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Plots will be unavailable.")


def get_episodes(db_path):
    """
    Extracts episodes from the clear table.

    Returns list of tuples: (id, type, start, end)

    Args:
        db_path: path to database

    Returns:
        List of episodes: [(id, type, start, end), ...]
    """
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type, start, end
            FROM clear
            ORDER BY start ASC
        """)
        episodes = cur.fetchall()

    print(f"Loaded {len(episodes)} episodes from database")
    return episodes


def calculate_durations(episodes):
    """
    Calculates duration of each episode and groups by opening type.

    Duration = (end - start) / 1000 / 60  -> in minutes

    Args:
        episodes: list of episodes from database

    Returns:
        Dictionary: {'manual': [durations], 'auto': [durations]}
    """
    durations = defaultdict(list)

    for episode_id, event_type, start, end in episodes:
        # Calculate duration in minutes
        duration_ms = end - start
        duration_minutes = duration_ms / 1000 / 60

        # Group by type
        durations[event_type].append(duration_minutes)

    print(f"Calculated durations:")
    print(f"  - manual: {len(durations.get('manual', []))} episodes")
    print(f"  - auto: {len(durations.get('auto', []))} episodes")

    return dict(durations)


def compute_descriptive_stats(durations):
    """
    Computes descriptive statistics for dataset.

    Metrics:
    - count: number of episodes
    - mean: arithmetic mean (sum of all values / count)
    - median: value that divides data in half (50% more, 50% less)
    - std: standard deviation (how spread out the data is)
    - min/max: minimum and maximum value
    - q25: 25th percentile (25% of data is less than this value)
    - q75: 75th percentile (75% of data is less than this value)

    Args:
        durations: list of durations

    Returns:
        Dictionary with metrics
    """
    if not durations:
        return {}

    sorted_durations = sorted(durations)
    n = len(sorted_durations)

    stats_dict = {
        'count': n,
        'mean': statistics.mean(durations),
        'median': statistics.median(durations),
        'std': statistics.stdev(durations) if n > 1 else 0.0,
        'min': min(durations),
        'max': max(durations),
        'q25': statistics.quantiles(durations, n=4)[0] if n >= 4 else sorted_durations[0],
        'q75': statistics.quantiles(durations, n=4)[2] if n >= 4 else sorted_durations[-1],
    }

    return stats_dict


def mann_whitney_test(group1, group2):
    """
    Performs Mann-Whitney U test to compare two independent groups.

    WHAT IS MANN-WHITNEY U TEST?
    Non-parametric test that checks if there is a statistically
    significant difference between two groups. Does not require
    normal distribution (unlike t-test).

    WHAT IS P-VALUE?
    p-value shows the probability that observed difference is random.
    - If p < 0.05: difference is statistically significant (reject H₀)
    - If p >= 0.05: difference may be random (do not reject H₀)

    H₀ (null hypothesis): "No difference between groups"
    H₁ (alternative): "There is a difference between groups"

    Args:
        group1: first data group
        group2: second data group

    Returns:
        Dictionary with test results: {'u_statistic': ..., 'p_value': ...}
    """
    if not SCIPY_AVAILABLE:
        return {'error': 'scipy not installed'}

    if len(group1) < 2 or len(group2) < 2:
        return {'error': 'Insufficient data for test (need at least 2 in each group)'}

    # Perform test
    u_statistic, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')

    return {
        'u_statistic': float(u_statistic),
        'p_value': float(p_value)
    }


def cliffs_delta(group1, group2):
    """
    Calculates Cliff's Delta - effect size measure.

    WHAT IS EFFECT SIZE?
    Even if p-value shows significant difference, it's important to understand
    HOW LARGE the difference is. Cliff's Delta shows this.

    Values:
    - δ = 0: no difference
    - δ = 1: all values in group1 are greater than all values in group2
    - δ = -1: all values in group1 are less than all values in group2

    Interpretation (Cohen):
    - |δ| < 0.147: negligible
    - 0.147 ≤ |δ| < 0.33: small
    - 0.33 ≤ |δ| < 0.474: medium
    - |δ| ≥ 0.474: large

    Args:
        group1: first group
        group2: second group

    Returns:
        Cliff's Delta value from -1 to 1
    """
    if not group1 or not group2:
        return 0.0

    # Count how many times values from group1 are greater than values from group2
    more = sum(1 for x in group1 for y in group2 if x > y)
    less = sum(1 for x in group1 for y in group2 if x < y)

    delta = (more - less) / (len(group1) * len(group2))
    return delta


def interpret_cliffs_delta(delta):
    """
    Interprets Cliff's Delta value.

    Args:
        delta: Cliff's Delta value

    Returns:
        Text interpretation
    """
    abs_delta = abs(delta)

    if abs_delta < 0.147:
        size = "negligible"
    elif abs_delta < 0.33:
        size = "small"
    elif abs_delta < 0.474:
        size = "medium"
    else:
        size = "large"

    direction = "higher" if delta > 0 else "lower"

    return f"{size} ({direction})"


def create_histogram(durations_by_type, output_path=None):
    """
    Creates histogram of duration distributions for both groups.

    WHY HISTOGRAM?
    Histogram shows how data is distributed. You can see:
    - Where most values concentrate
    - If there are outliers (very large or small values)
    - If distribution is symmetric

    Args:
        durations_by_type: dictionary {'manual': [...], 'auto': [...]}
        output_path: path to save (if None, returns base64)

    Returns:
        File path or base64 string of image
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    manual_durations = durations_by_type.get('manual', [])
    auto_durations = durations_by_type.get('auto', [])

    # Use log scale for better visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Filter to reasonable range (up to 95th percentile) for readability
    manual_95 = np.percentile(manual_durations, 95) if manual_durations else 60
    auto_95 = np.percentile(auto_durations, 95) if auto_durations else 60

    manual_filtered = [d for d in manual_durations if d <= manual_95]
    auto_filtered = [d for d in auto_durations if d <= auto_95]

    # Manual histogram
    ax1.hist(manual_filtered, bins=50, color='#4A90E2', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Duration (minutes)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Number of Episodes', fontsize=11, fontweight='bold')
    ax1.set_title(f'Manual Openings Distribution (up to 95th percentile)\nn={len(manual_filtered)} of {len(manual_durations)} episodes',
                  fontsize=12, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.axvline(np.median(manual_filtered), color='red', linestyle='--', linewidth=2, label=f'Median: {np.median(manual_filtered):.2f} min')
    ax1.legend()

    # Auto histogram
    ax2.hist(auto_filtered, bins=50, color='#E94B3C', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax2.set_xlabel('Duration (minutes)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Number of Episodes', fontsize=11, fontweight='bold')
    ax2.set_title(f'Auto Openings Distribution (up to 95th percentile)\nn={len(auto_filtered)} of {len(auto_durations)} episodes',
                  fontsize=12, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.axvline(np.median(auto_filtered), color='red', linestyle='--', linewidth=2, label=f'Median: {np.median(auto_filtered):.2f} min')
    ax2.legend()

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        return img_base64


def create_boxplot(durations_by_type, output_path=None):
    """
    Creates box plot to compare groups.

    WHAT IS BOX PLOT?
    Box plot shows:
    - Median (line in center of box)
    - 25th and 75th percentiles (box boundaries)
    - Min and max (whiskers)
    - Outliers (points beyond whiskers)

    Very visual way to compare distributions!

    Args:
        durations_by_type: dictionary {'manual': [...], 'auto': [...]}
        output_path: path to save (if None, returns base64)

    Returns:
        File path or base64 string of image
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    manual_durations = durations_by_type.get('manual', [])
    auto_durations = durations_by_type.get('auto', [])

    # Filter outliers for better readability (keep up to 95th percentile)
    manual_95 = np.percentile(manual_durations, 95) if manual_durations else 0
    auto_95 = np.percentile(auto_durations, 95) if auto_durations else 0

    manual_filtered = [d for d in manual_durations if d <= manual_95]
    auto_filtered = [d for d in auto_durations if d <= auto_95]

    fig, ax = plt.subplots(figsize=(10, 7))

    bp = ax.boxplot([manual_filtered, auto_filtered],
                     tick_labels=['Manual', 'Auto'],
                     patch_artist=True,
                     showmeans=True,
                     meanprops=dict(marker='D', markerfacecolor='green', markersize=8),
                     medianprops=dict(color='red', linewidth=2),
                     boxprops=dict(linewidth=1.5),
                     whiskerprops=dict(linewidth=1.5),
                     capprops=dict(linewidth=1.5))

    # Color boxes
    bp['boxes'][0].set_facecolor('#4A90E2')
    bp['boxes'][0].set_alpha(0.7)
    bp['boxes'][1].set_facecolor('#E94B3C')
    bp['boxes'][1].set_alpha(0.7)

    ax.set_ylabel('Duration (minutes)', fontsize=12, fontweight='bold')
    ax.set_title('Episode Duration Comparison\n(up to 95th percentile)', fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')

    # Add median values as text
    manual_median = statistics.median(manual_filtered)
    auto_median = statistics.median(auto_filtered)
    ax.text(1, manual_median, f'  Median: {manual_median:.2f}', va='center', fontsize=10, fontweight='bold')
    ax.text(2, auto_median, f'  Median: {auto_median:.2f}', va='center', fontsize=10, fontweight='bold')

    # Add count information
    ax.text(0.02, 0.98, f'Manual: n={len(manual_filtered)} (of {len(manual_durations)})',
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax.text(0.02, 0.92, f'Auto: n={len(auto_filtered)} (of {len(auto_durations)})',
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        return img_base64


def create_comparison_plot(durations_by_type, stats_by_type, output_path=None):
    """
    Creates comprehensive comparison chart of means, medians and quartiles.

    Args:
        durations_by_type: dictionary {'manual': [...], 'auto': [...]}
        stats_by_type: dictionary {'manual': {...}, 'auto': {...}}
        output_path: path to save (if None, returns base64)

    Returns:
        File path or base64 string of image
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    manual_stats = stats_by_type.get('manual', {})
    auto_stats = stats_by_type.get('auto', {})

    if not manual_stats or not auto_stats:
        return None

    fig, ax = plt.subplots(figsize=(11, 7))

    metrics = ['Median', 'Mean', '25th Perc.', '75th Perc.']
    manual_values = [
        manual_stats['median'],
        manual_stats['mean'],
        manual_stats['q25'],
        manual_stats['q75']
    ]
    auto_values = [
        auto_stats['median'],
        auto_stats['mean'],
        auto_stats['q25'],
        auto_stats['q75']
    ]

    x = np.arange(len(metrics))
    width = 0.35

    bars1 = ax.bar(x - width/2, manual_values, width, label='Manual',
                   color='#4A90E2', alpha=0.8, edgecolor='black', linewidth=1)
    bars2 = ax.bar(x + width/2, auto_values, width, label='Auto',
                   color='#E94B3C', alpha=0.8, edgecolor='black', linewidth=1)

    ax.set_ylabel('Duration (minutes)', fontsize=12, fontweight='bold')
    ax.set_title('Key Metrics Comparison', fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontweight='bold')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')

    # Add values on bars
    def autolabel(bars):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')

    autolabel(bars1)
    autolabel(bars2)

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
        return img_base64


def analyze_data(db_path, create_plots=True):
    """
    Main data analysis function.

    Performs complete statistical analysis:
    1. Loads data from database
    2. Calculates durations
    3. Computes descriptive statistics for each group
    4. Performs Mann-Whitney U test
    5. Calculates effect size (Cliff's Delta)
    6. Creates plots (optional)

    Args:
        db_path: path to database
        create_plots: whether to create plots (default True)

    Returns:
        Dictionary with all analysis results, including plots in base64
    """
    print("\n" + "="*60)
    print("STATISTICAL DATA ANALYSIS")
    print("="*60 + "\n")

    # Step 1: Load data
    print("Step 1: Loading data from database...")
    episodes = get_episodes(db_path)

    if not episodes:
        print("Error: no data in clear table")
        return {}

    # Step 2: Calculate durations
    print("\nStep 2: Calculating durations...")
    durations_by_type = calculate_durations(episodes)

    manual_durations = durations_by_type.get('manual', [])
    auto_durations = durations_by_type.get('auto', [])

    if not manual_durations or not auto_durations:
        print("Error: insufficient data for both groups")
        return {}

    # Step 3: Descriptive statistics
    print("\nStep 3: Computing descriptive statistics...")
    manual_stats = compute_descriptive_stats(manual_durations)
    auto_stats = compute_descriptive_stats(auto_durations)

    print(f"\nMANUAL GROUP STATISTICS:")
    print(f"  Count: {manual_stats['count']}")
    print(f"  Mean: {manual_stats['mean']:.2f} min")
    print(f"  Median: {manual_stats['median']:.2f} min")
    print(f"  Std: {manual_stats['std']:.2f} min")

    print(f"\nAUTO GROUP STATISTICS:")
    print(f"  Count: {auto_stats['count']}")
    print(f"  Mean: {auto_stats['mean']:.2f} min")
    print(f"  Median: {auto_stats['median']:.2f} min")
    print(f"  Std: {auto_stats['std']:.2f} min")

    # Step 4: Mann-Whitney U test
    print("\nStep 4: Performing Mann-Whitney U test...")
    test_result = mann_whitney_test(manual_durations, auto_durations)

    if 'error' in test_result:
        print(f"Test error: {test_result['error']}")
    else:
        print(f"U-statistic: {test_result['u_statistic']:.2f}")
        print(f"p-value: {test_result['p_value']:.6f}")

        if test_result['p_value'] < 0.05:
            print("Result: STATISTICALLY SIGNIFICANT DIFFERENCE (p < 0.05)")
            print("  -> Can reject null hypothesis H₀")
            print("  -> Episode duration differs between groups")
        else:
            print("Result: NO STATISTICALLY SIGNIFICANT DIFFERENCE (p >= 0.05)")
            print("  -> Cannot reject null hypothesis H₀")
            print("  -> Difference may be random")

    # Step 5: Effect size (Cliff's Delta)
    print("\nStep 5: Computing effect size (Cliff's Delta)...")
    delta = cliffs_delta(manual_durations, auto_durations)
    interpretation = interpret_cliffs_delta(delta)

    print(f"Cliff's Delta: {delta:.4f}")
    print(f"Interpretation: {interpretation}")

    if delta > 0:
        print("  -> Manual durations are HIGHER than Auto")
    else:
        print("  -> Manual durations are LOWER than Auto")

    # Collect all results
    results = {
        'manual': {
            'durations': manual_durations,
            'stats': manual_stats
        },
        'auto': {
            'durations': auto_durations,
            'stats': auto_stats
        },
        'test': test_result,
        'effect_size': {
            'cliffs_delta': delta,
            'interpretation': interpretation
        }
    }

    # Step 6: Create plots
    if create_plots and MATPLOTLIB_AVAILABLE:
        print("\nStep 6: Creating plots...")

        stats_by_type = {'manual': manual_stats, 'auto': auto_stats}

        results['plots'] = {
            'histogram': create_histogram(durations_by_type),
            'boxplot': create_boxplot(durations_by_type),
            'comparison': create_comparison_plot(durations_by_type, stats_by_type)
        }

        print("Plots created (base64)")

    print("\n" + "="*60)
    print("ANALYSIS COMPLETED")
    print("="*60 + "\n")

    return results


def main():
    """
    Entry point for running analysis from command line.
    """
    # Define paths
    project_root = Path(__file__).parent.parent
    db_path = resolver.db_path()

    # Run analysis
    results = analyze_data(str(db_path))

    if results:
        # Save plots as files for viewing
        if 'plots' in results and MATPLOTLIB_AVAILABLE:
            plots_dir = project_root / 'plots'
            plots_dir.mkdir(exist_ok=True)

            # Recreate plots as files
            durations_by_type = {'manual': results['manual']['durations'],
                                'auto': results['auto']['durations']}
            stats_by_type = {'manual': results['manual']['stats'],
                           'auto': results['auto']['stats']}

            create_histogram(durations_by_type, plots_dir / 'histogram.png')
            create_boxplot(durations_by_type, plots_dir / 'boxplot.png')
            create_comparison_plot(durations_by_type, stats_by_type, plots_dir / 'comparison.png')

            print(f"\nPlots saved to: {plots_dir}")


if __name__ == '__main__':
    main()