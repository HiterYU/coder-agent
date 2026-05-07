MISTAKE_TAXONOMY = {
    "problem_understanding_wrong": "题意理解错误",
    "boundary_condition_missing": "漏边界条件",
    "index_out_of_range": "下标越界",
    "wrong_loop_condition": "循环条件错误",
    "wrong_state_definition": "状态定义错误",
    "wrong_state_transition": "状态转移错误",
    "recursion_base_case_missing": "递归终止条件错误",
    "visited_handling_wrong": "visited 处理错误",
    "greedy_reasoning_weak": "贪心理由不充分",
    "complexity_too_high": "复杂度过高",
    "return_format_wrong": "返回格式错误",
}


TOPIC_ALIASES = {
    "Array": "array",
    "Hash Table": "hash_table",
    "Stack": "stack",
    "Binary Search": "binary_search",
    "Two Pointers": "two_pointers",
    "Sliding Window": "sliding_window",
    "Linked List": "linked_list",
    "Dynamic Programming": "dynamic_programming",
    "Depth-First Search": "graph_search",
    "Breadth-First Search": "graph_search",
    "Tree": "tree",
    "Graph": "graph",
    "Sorting": "sorting",
}


def normalize_topic(tag: str) -> str:
    return TOPIC_ALIASES.get(tag, tag.lower().replace(" ", "_"))
