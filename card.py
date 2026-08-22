import os
import sys

# 扑克牌花色与符号定义
SUITS = {
    'S': '♠️',  # 黑桃
    'H': '❤️',  # 红桃
    'C': '♣️',  # 梅花
    'D': '💎'  # 方块
}
SUIT_NAMES = {'S': '黑桃', 'H': '红桃', 'C': '梅花', 'D': '方块'}
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']


def clear_screen():
    """跨平台清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_all_cards():
    """生成54张牌的列表，返回 [(suit, rank), ...]"""
    cards = []
    for suit in SUITS:
        for rank in RANKS:
            cards.append((suit, rank))
    # 追加大小王
    cards.append(('J', 'Small'))  # 小王
    cards.append(('J', 'Big'))  # 大王
    return cards


def display_cards(collected_set):
    """在终端以网格形式展示所有牌，已收集的显示高亮"""
    clear_screen()
    print("=" * 75)
    print(" 🃏 扑克牌记牌器 (输入编号点亮/熄灭，如: 1 或 1,3,5 | 输入 q 退出)")
    print("=" * 75)

    all_cards = get_all_cards()
    # 按每行 14 张排列，方便大小王独立成行
    for i, (suit, rank) in enumerate(all_cards):
        idx = i + 1

        # 处理大小王的特殊显示
        if suit == 'J':
            card_str = "🃏小王" if rank == 'Small' else "🃏大王"
        else:
            card_str = f"{SUITS[suit]}{rank}"

        # 如果已收集，加上高亮背景色
        if idx in collected_set:
            display = f"\033[42;30m {idx:>2}:{card_str:<6} \033[0m"  # 绿底黑字
        else:
            display = f" {idx:>2}:{card_str:<6} "

        print(display, end="")
        # 每 14 张换行
        if idx % 14 == 0:
            print()
    print("=" * 75)
    print(f" 📊 当前进度: {len(collected_set)} / 54")


def print_missing_cards(collected_set):
    """程序结束时，按花色分类输出未收集的牌"""
    all_cards = get_all_cards()
    missing = {suit: [] for suit in SUITS}
    missing['J'] = []  # 专门用来存大小王

    for i, (suit, rank) in enumerate(all_cards):
        if (i + 1) not in collected_set:
            if suit == 'J':
                missing['J'].append("小王" if rank == 'Small' else "大王")
            else:
                missing[suit].append(rank)

    clear_screen()
    print("\n" + "=" * 40)
    print(" 📋 结算：您还未收集的牌如下：")
    print("=" * 40)

    total_missing = 0
    for suit in list(SUITS.keys()) + ['J']:
        ranks = missing[suit]
        total_missing += len(ranks)

        if suit == 'J':
            name = "🃏 王牌"
        else:
            name = f"{SUITS[suit]} {SUIT_NAMES[suit]}"

        if ranks:
            cards_str = " ".join(ranks)
            print(f" {name:<6}: {cards_str}")
        else:
            print(f" {name:<6}: ✅ 已集齐！")

    print("-" * 40)
    if total_missing == 0:
        print(" 🎉 恭喜！您已经收集齐了整副扑克牌（含大小王）！")
    else:
        print(f" 🎯 还差 {total_missing} 张牌，继续加油！")
    print("=" * 40 + "\n")


def main():
    collected = set()  # 存储已点亮牌的编号 (1-54)

    while True:
        display_cards(collected)
        user_input = input(" 👉 请输入操作: ").strip().lower()

        if user_input == 'q':
            break

        # 支持逗号或空格分隔的多个数字
        inputs = user_input.replace(',', ' ').split()
        valid_nums = []

        for num_str in inputs:
            if num_str.isdigit():
                num = int(num_str)
                if 1 <= num <= 54:
                    valid_nums.append(num)

        # 切换选中状态（点亮/熄灭）
        for num in valid_nums:
            if num in collected:
                collected.remove(num)
            else:
                collected.add(num)

    # 退出前输出缺失的牌
    print_missing_cards(collected)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 检测到强制退出，正在生成结算报告...")
        sys.exit(0)