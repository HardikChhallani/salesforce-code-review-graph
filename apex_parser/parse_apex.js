import { ApexParserFactory } from "@apexdevtools/apex-parser";
import fs from "fs";

const filePath = process.argv[2];

if (!filePath) {
    console.error("Usage: node parse_apex.js <file_path>");
    process.exit(1);
}

let code;
try {
    code = fs.readFileSync(filePath, "utf-8");
} catch (err) {
    console.error(`Error reading file: ${err.message}`);
    process.exit(1);
}

const parser = ApexParserFactory.createParser(code);

let tree;

// Detect trigger vs class
if (filePath.endsWith(".trigger")) {
    tree = parser.triggerUnit();
} else {
    tree = parser.compilationUnit();
}

// Serialize AST with line info from ANTLR context
function serialize(node) {
    if (!node) return null;

    const result = {
        type: node.constructor.name,
        text: node.getText ? node.getText() : "",
    };

    // Add line numbers from ANTLR token positions
    if (node.start) {
        result.startLine = node.start.line;
        result.startCol = node.start.column;
    }
    if (node.stop) {
        result.endLine = node.stop.line;
        result.endCol = node.stop.column;
    }

    // Collect children from parser rule contexts
    if (node.children && node.children.length > 0) {
        result.children = node.children
            .map(serialize)
            .filter(c => c !== null);
    } else {
        result.children = [];
    }

    return result;
}

console.log(JSON.stringify(serialize(tree)));