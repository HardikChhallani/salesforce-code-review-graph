from tree_sitter import Language

Language.build_library(
    "build/my-languages.so",
    [
        "vendor/tree-sitter-sfapex/apex",
    ]
)