#!/usr/bin/env python3
"""
Monitor active contrarian positions until settlement
"""

import os
import sys
import yaml
import time
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.live import Live

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.polymarket import PolymarketMechanics
from src.core.market_15m import Market15M

console = Console()

def get_position_status(pm, order_id, coin, direction):
    """Get detailed status of a position"""
    try:
        order = pm.client.get_order(order_id)

        status = order.get('status', 'UNKNOWN')
        size = float(order.get('original_size', 0))
        matched = float(order.get('size_matched', 0))
        price = float(order.get('price', 0))

        # Calculate current value (if we can get current price)
        current_value = 0
        pnl = 0
        pnl_pct = 0

        return {
            'coin': coin,
            'direction': direction,
            'order_id': order_id[:16] + '...',
            'status': status,
            'shares': matched,
            'entry_price': price,
            'cost': 1.00,  # All were $1.00 orders
            'current_value': current_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        }
    except Exception as e:
        return {
            'coin': coin,
            'direction': direction,
            'order_id': order_id[:16] + '...',
            'status': 'ERROR',
            'shares': 0,
            'entry_price': 0,
            'cost': 1.00,
            'current_value': 0,
            'pnl': 0,
            'pnl_pct': 0,
            'error': str(e)
        }

def create_dashboard(positions, elapsed_time):
    """Create rich table dashboard"""

    table = Table(title=f"🎯 Contrarian Position Monitor (Running {elapsed_time}s)")

    table.add_column("Coin", style="cyan")
    table.add_column("Dir", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Shares", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("P&L", justify="right")

    total_cost = 0
    total_pnl = 0

    for pos in positions:
        # Color code status
        status = pos['status']
        if status == 'MATCHED':
            status_display = "[green]MATCHED[/green]"
        elif status == 'LIVE':
            status_display = "[yellow]LIVE[/yellow]"
        elif status == 'ERROR':
            status_display = "[red]ERROR[/red]"
        else:
            status_display = status

        # Color code P&L
        pnl = pos['pnl']
        if pnl > 0:
            pnl_display = f"[green]+${pnl:.2f}[/green]"
        elif pnl < 0:
            pnl_display = f"[red]-${abs(pnl):.2f}[/red]"
        else:
            pnl_display = f"${pnl:.2f}"

        table.add_row(
            pos['coin'],
            pos['direction'],
            status_display,
            f"{pos['shares']:.2f}",
            f"${pos['entry_price']:.3f}",
            f"${pos['cost']:.2f}",
            pnl_display
        )

        total_cost += pos['cost']
        total_pnl += pos['pnl']

    # Add totals
    table.add_section()
    total_pnl_display = f"[green]+${total_pnl:.2f}[/green]" if total_pnl > 0 else (f"[red]-${abs(total_pnl):.2f}[/red]" if total_pnl < 0 else f"${total_pnl:.2f}")
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        "",
        "",
        f"[bold]${total_cost:.2f}[/bold]",
        f"[bold]{total_pnl_display}[/bold]"
    )

    return table

def main():
    load_dotenv()

    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize Polymarket
    funder = config['polymarket'].get('funder')
    if funder == "0x...":
        funder = None

    pm = PolymarketMechanics(
        private_key=os.getenv('WALLET_PRIVATE_KEY'),
        chain_id=config['polymarket'].get('chain_id', 137),
        signature_type=config['polymarket'].get('signature_type', 0),
        funder=funder
    )

    # The 4 orders we're monitoring
    positions = [
        {'order_id': '0x32e03eb4d1019e5ea685a4c4bd9719255220acc8248d12b1d3251a445138260b', 'coin': 'BTC', 'direction': 'UP'},
        {'order_id': '0x458c2686f4c82ad857bfad838e57af61569eb8313b1ae3840fe8e737cca84f7f', 'coin': 'SOL', 'direction': 'UP'},
        {'order_id': '0xf0353f82b3371750b90b15d494546eccf1c72990635328fa990cb1f3b4b0c144', 'coin': 'BTC', 'direction': 'UP'},
        {'order_id': '0xd09d42af6d2f0c70114beab29bdc1a29d278a684ba52b1c1a65c942ee88adc58', 'coin': 'SOL', 'direction': 'UP'}
    ]

    console.print("\n[bold yellow]Starting Position Monitor[/bold yellow]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")

    start_time = time.time()

    try:
        while True:
            elapsed = int(time.time() - start_time)

            # Get status of all positions
            position_statuses = []
            for pos in positions:
                status = get_position_status(pm, pos['order_id'], pos['coin'], pos['direction'])
                position_statuses.append(status)

            # Create and display dashboard
            dashboard = create_dashboard(position_statuses, elapsed)
            console.clear()
            console.print(dashboard)

            # Check if all positions settled
            all_settled = all(pos['status'] not in ['MATCHED', 'LIVE'] for pos in position_statuses)
            if all_settled:
                console.print("\n[green]✓ All positions settled![/green]")
                break

            # Wait 10 seconds before next check
            time.sleep(10)

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")

if __name__ == "__main__":
    main()
