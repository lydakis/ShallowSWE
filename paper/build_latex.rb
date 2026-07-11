#!/usr/bin/env ruby
# frozen_string_literal: true

require "fileutils"
require "kramdown"

abort "usage: build_latex.rb SOURCE.md OUTPUT.tex" unless ARGV.length == 2

source_path, output_path = ARGV
markdown = File.read(source_path, encoding: "UTF-8")

# The title block and references are represented structurally in the LaTeX wrapper/BibTeX file.
markdown = markdown.sub(/\A# .*?\n\n/m, "")
markdown = markdown.sub(/\A\*\*Methodology White Paper.*?\n\*\*July 2026\*\*\n\n/m, "")
markdown = markdown.sub(/^## Abstract\n/, "")
markdown = markdown.sub(/^# References\n.*\z/m, "")
status_note = markdown.slice!(/\A> \*\*Freeze candidate.*?\n\nShallowSWE is an independent.*?authors\.\n\n/m)&.strip
abort "could not locate publication status note" unless status_note

# Kramdown's native math delimiter is $$...$$ for both inline and display math.
# Preserve fenced code before normalizing the source's LaTeX-style delimiters.
chunks = markdown.split(/(^```.*?^```\s*$)/m)
chunks.each_with_index do |chunk, index|
  next if index.odd?

  chunk.gsub!(/\\\((.+?)\\\)/m, '$$\1$$')
  chunk.gsub!(/^\\\[\s*$/, "$$")
  chunk.gsub!(/^\\\]\s*$/, "$$")
end
markdown = chunks.join

body = Kramdown::Document.new(
  markdown,
  input: "GFM",
  math_engine: nil,
  syntax_highlighter: nil
).to_latex

# Restore the paper's explicit numbering without duplicating it in section titles.
body.gsub!(/\\subsection\{(?:\d+\. )?([^}]*)\}/, '\\section{\1}')
body.gsub!(/\\subsubsection\{(?:\d+\.\d+ )?([^}]*)\}/, '\\subsection{\1}')
body.gsub!(/\\section\{Appendix ([A-C])\. ([^}]*)\}/, '\\appendixsection{\1}{\2}')
body.gsub!(/\\subsection\{[A-C]\.\d+ ([^}]*)\}/, '\\subsection{\1}')
body.gsub!(/\\section\{[A-C]\.\d+ ([^}]*)\}/, '\\subsection{\1}')
body.sub!('\\appendixsection{A}', "\\appendix\n\\appendixsection{A}")

# Convert bracketed source references to numeric BibTeX citations.
keys = {
  "1" => "huang2026deepswe",
  "2" => "jimenez2024swebench",
  "3" => "miserendino2025swelancer",
  "4" => "minisweagent2026"
}
keys.each { |number, key| body.gsub!("{[}#{number}{]}", "\\citep{#{key}}") }

# Use local, extension-free figure paths so both pdfLaTeX and arXiv resolve assets reliably.
body.gsub!(/\\includegraphics\{(?:ShallowSWE_v0\.4\.1_assets|\.\.\/paper\/figures)\/(figure[123]_\w+)\.png\}/,
           '\\includegraphics[width=0.96\\linewidth]{figures/\1}')
body.gsub!(/\\begin\{figure\}/, '\\begin{figure}[tbp]')
body.gsub!(/\\begin\{figure\}\[tbp\]/, '\\begin{figure}[H]')
body.gsub!(/\\caption\{Figure [1-3]\. /, '\\caption{')

# Kramdown renders source display delimiters as multiline inline math. Restore display equations.
body.gsub!(/\n\$(.+?)\$\\newline\n/m) { "\n\\[\n#{$1.strip}\n\\]\n" }

# Kramdown emits non-wrapping longtable columns. Paragraph columns keep the paper within margins.
body.gsub!('\\begin{longtable}{|l|l|l|}',
           '\\begin{longtable}{@{}p{0.22\\linewidth}p{0.16\\linewidth}p{0.56\\linewidth}@{}}')
body.gsub!('\\begin{longtable}{|l|r|l|}',
           '\\begin{longtable}{@{}p{0.18\\linewidth}p{0.26\\linewidth}p{0.50\\linewidth}@{}}')
body.gsub!('\\begin{longtable}{|l|r|r|}',
           '\\begin{longtable}{@{}p{0.48\\linewidth}p{0.20\\linewidth}p{0.24\\linewidth}@{}}')
body.sub!("\\hline\n", "\\toprule\n")
body.gsub!('language=text,', '')
body.gsub!('“', '``')
body.gsub!('”', "''")

# Abstract is the prose before the first numbered section.
abstract, rest = body.split(/(?=\\section\{Introduction\})/, 2)
abort "could not locate Introduction section" unless rest

preamble = <<~'LATEX'
  \documentclass[11pt]{article}

  \usepackage[T1]{fontenc}
  \usepackage[utf8]{inputenc}
  \usepackage{lmodern}
  \usepackage{microtype}
  \usepackage[letterpaper,margin=1in]{geometry}
  \usepackage{amsmath,amssymb,mathtools}
  \usepackage{graphicx}
  \usepackage{float}
  \usepackage{booktabs,longtable,array}
  \usepackage{enumitem}
  \usepackage{xcolor}
  \usepackage{listings}
  \usepackage[numbers,sort&compress]{natbib}
  \usepackage[hidelinks]{hyperref}
  \usepackage[nameinlink,noabbrev]{cleveref}

  \definecolor{codegray}{RGB}{247,247,247}
  \lstset{
    basicstyle=\ttfamily\small,
    backgroundcolor=\color{codegray},
    frame=single,
    framerule=0.2pt,
    breaklines=true,
    columns=fullflexible,
    keepspaces=true,
    showstringspaces=false
  }
  \setlist{nosep,leftmargin=*}
  \setlength{\emergencystretch}{2em}
  \renewcommand{\arraystretch}{1.15}
  \newcommand{\appendixsection}[2]{\section{#2}}

  \title{\textbf{ShallowSWE: Measuring Reference-Budget Cost per Verified Completion on Routine Software Work}\\[0.5em]
  \large Methodology White Paper -- Freeze Candidate v0.4.2}
  \author{George Lydakis\\\href{mailto:george@lydakis.me}{george@lydakis.me}}
  \date{July 2026}

  \hypersetup{
    pdftitle={ShallowSWE: Measuring Reference-Budget Cost per Verified Completion on Routine Software Work},
    pdfauthor={George Lydakis},
  pdfsubject={Methodology White Paper -- Freeze Candidate v0.4.2},
    pdfkeywords={ShallowSWE, software engineering agents, benchmark, CPSC, repair loop, cost efficiency}
  }

  \begin{document}
  \maketitle

  \begin{center}
  \small\itshape
Freeze candidate v0.4.2. This paper defines the intended protocol. The
  implementation-status boundary reflects the repository audit dated July 11,
  2026 and must be replaced with an exact commit SHA before publication.\\[0.4em]
  ShallowSWE is independent and is not affiliated with DeepSWE, SWE-bench,
  SWE-Lancer, Datacurve, Harbor, Pier, or their authors.
  \end{center}
  \vspace{0.5em}

  \begin{abstract}
LATEX

postamble = <<~'LATEX'

  \bibliographystyle{plainnat}
  \nocite{minisweagent2026}
  \bibliography{references}

  \end{document}
LATEX

document = preamble + abstract.strip + "\n\\end{abstract}\n\n" + rest.strip + postamble
FileUtils.mkdir_p(File.dirname(output_path))
File.write(output_path, document, encoding: "UTF-8")
