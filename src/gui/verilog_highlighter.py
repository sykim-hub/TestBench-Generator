import sys
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter

class VerilogHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlightingRules = []

        # 1. General Identifiers (Cyan) - applied first so keywords can overwrite them
        identifierFormat = QTextCharFormat()
        identifierFormat.setForeground(QColor("#56b6c2")) # Cyan
        self.highlightingRules.append((QRegularExpression("\\b[a-zA-Z_][a-zA-Z0-9_]*\\b"), identifierFormat))

        # 2. Keywords (Purple/Pink)
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#c678dd")) # Pinkish purple
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\bmodule\\b", "\\bendmodule\\b", "\\binput\\b", "\\boutput\\b", "\\binout\\b",
            "\\bwire\\b", "\\breg\\b", "\\bassign\\b", "\\balways\\b", "\\binitial\\b",
            "\\bbegin\\b", "\\bend\\b", "\\bif\\b", "\\belse\\b", "\\bfor\\b", "\\bwhile\\b",
            "\\bcase\\b", "\\bendcase\\b", "\\btask\\b", "\\bendtask\\b", "\\bfunction\\b",
            "\\bendfunction\\b", "\\bparameter\\b", "\\blocalparam\\b", "\\bdefparam\\b",
            "\\bgenvar\\b", "\\bgenerate\\b", "\\bendgenerate\\b", "\\bposedge\\b", "\\bnegedge\\b",
            "\\bor\\b", "\\band\\b", "\\blogic\\b", "\\bbit\\b", "\\bint\\b", "\\benum\\b",
            "\\bstruct\\b", "\\btypedef\\b", "\\bpackage\\b", "\\bendpackage\\b"
        ]
        for pattern in keywords:
            self.highlightingRules.append((QRegularExpression(pattern), keywordFormat))

        # 3. Numbers (Orange)
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#d19a66"))
        self.highlightingRules.append((QRegularExpression("\\b\\d+'[bBoOdDhH][0-9a-fA-F_xXzZ]+\\b"), numberFormat))
        self.highlightingRules.append((QRegularExpression("\\b\\d+\\b"), numberFormat))

        # 4. System Tasks (Blue)
        sysTaskFormat = QTextCharFormat()
        sysTaskFormat.setForeground(QColor("#61afef"))
        self.highlightingRules.append((QRegularExpression("\\$[a-zA-Z0-9_]+\\b"), sysTaskFormat))

        # 5. Strings (Green)
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#98c379"))
        self.highlightingRules.append((QRegularExpression("\".*\""), stringFormat))

        # 6. Single Line Comments (Grey, Italic)
        self.singleLineCommentFormat = QTextCharFormat()
        self.singleLineCommentFormat.setForeground(QColor("#5c6370"))
        self.singleLineCommentFormat.setFontItalic(True)
        self.highlightingRules.append((QRegularExpression("//[^\n]*"), self.singleLineCommentFormat))
        self.highlightingRules.append((QRegularExpression("--[^\n]*"), self.singleLineCommentFormat))

        # 7. Multi Line Comments (Grey, Italic) -> Handled in highlightBlock
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#5c6370"))
        self.multiLineCommentFormat.setFontItalic(True)
        self.commentStartExpression = QRegularExpression("/\\*")
        self.commentEndExpression = QRegularExpression("\\*/")

    def highlightBlock(self, text):
        # Apply standard rules
        for pattern, format in self.highlightingRules:
            matchIterator = pattern.globalMatch(text)
            while matchIterator.hasNext():
                match = matchIterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

        # Apply multi-line comment logic
        self.setCurrentBlockState(0)

        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = text.find("/*")
            # Ignore /* if it is part of a single line comment //
            singleLineCommentIndex = text.find("//")
            if singleLineCommentIndex != -1 and startIndex > singleLineCommentIndex:
                startIndex = -1 # Cancel the block comment start
            
        while startIndex >= 0:
            endIndex = text.find("*/", startIndex)
            commentLength = 0
            
            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else:
                commentLength = endIndex - startIndex + 2 # length of "*/"
                
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            
            # Find next block comment start, ensuring we don't pick one up inside a single-line comment
            nextStartIndex = text.find("/*", startIndex + commentLength)
            singleLineCommentIndex = text.find("//", startIndex + commentLength)
            
            if singleLineCommentIndex != -1 and nextStartIndex > singleLineCommentIndex:
                startIndex = -1 # It's just a /* inside a // comment
            else:
                startIndex = nextStartIndex
