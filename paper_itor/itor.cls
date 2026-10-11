%%
%% This is file `itor.cls',
%% generated with the docstrip utility.
%%
%% Copyright (c) ITOR.
%% 
%% \CharacterTable
%%  {Upper-case    \A\B\C\D\E\F\G\H\I\J\K\L\M\N\O\P\Q\R\S\T\U\V\W\X\Y\Z
%%   Lower-case    \a\b\c\d\e\f\g\h\i\j\k\l\m\n\o\p\q\r\s\t\u\v\w\x\y\z
%%   Digits        \0\1\2\3\4\5\6\7\8\9
%%   Exclamation   \!     Double quote  \"     Hash (number) \#
%%   Dollar        \$     Percent       \%     Ampersand     \&
%%   Acute accent  \'     Left paren    \(     Right paren   \)
%%   Asterisk      \*     Plus          \+     Comma         \,
%%   Minus         \-     Point         \.     Solidus       \/
%%   Colon         \:     Semicolon     \;     Less than     \<
%%   Equals        \=     Greater than  \>     Question mark \?
%%   Commercial at \@     Left bracket  \[     Backslash     \\
%%   Right bracket \]     Circumflex    \^     Underscore    \_
%%   Grave accent  \`     Left brace    \{     Vertical bar  \|
%%   Right brace   \}     Tilde         \~}
\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{itor}[2015/12/24 v1.0 Standard LaTeX document class]
\newif\if@restonecol
\DeclareOption{a4paper}
   {\setlength\paperheight {297mm}%
    \setlength\paperwidth  {210mm}}
\DeclareOption{a5paper}
   {\setlength\paperheight {210mm}%
    \setlength\paperwidth  {148mm}}
\DeclareOption{b5paper}
   {\setlength\paperheight {250mm}%
    \setlength\paperwidth  {176mm}}
\DeclareOption{letterpaper}
   {\setlength\paperheight {11in}%
    \setlength\paperwidth  {8.5in}}
\DeclareOption{legalpaper}
   {\setlength\paperheight {14in}%
    \setlength\paperwidth  {8.5in}}
\DeclareOption{executivepaper}
   {\setlength\paperheight {10.5in}%
    \setlength\paperwidth  {7.25in}}
\DeclareOption{landscape}
   {\setlength\@tempdima   {\paperheight}%
    \setlength\paperheight {\paperwidth}%
    \setlength\paperwidth  {\@tempdima}}
%
\DeclareOption{oneside}{\@twosidefalse \@mparswitchfalse}
\DeclareOption{twoside}{\@twosidetrue  \@mparswitchtrue}
\DeclareOption{draft}{\setlength\overfullrule{5pt}}
\DeclareOption{final}{\setlength\overfullrule{0pt}}
\DeclareOption{onecolumn}{\@twocolumnfalse}
\DeclareOption{twocolumn}{\@twocolumntrue}
\DeclareOption{fleqn}{\PassOptionsToPackage{fleqn}{amsmath}\input{fleqn.clo}}
\DeclareOption{unnumberedheads}{\AtEndOfClass{\setcounter{secnumdepth}{0}}}%
\DeclareOption{openbib}{%
  \AtEndOfPackage{%
   \renewcommand\@openbib@code{%
      \advance\leftmargin\bibindent
      \itemindent -\bibindent
      \listparindent \itemindent
      \parsep \z@
      }%
   \renewcommand\newblock{\par}}%
}
\ExecuteOptions{letterpaper,fleqn,twoside,onecolumn,final}
\ProcessOptions
%
%%%%%%%%%%%  Aptara Input %%%%%
\renewcommand\rmdefault{ptm}%
\renewcommand\sfdefault{phv}%
\RequirePackage{graphicx}%

\renewcommand\normalsize{%
   \@setfontsize\normalsize{11}{13}
   \abovedisplayskip 10\p@ \@plus2\p@ \@minus.5\p@
   \abovedisplayshortskip \z@ \@plus3\p@
   \belowdisplayshortskip 6\p@ \@plus3\p@ \@minus3\p@
   \belowdisplayskip \abovedisplayskip
   \let\@listi\@listI}
\normalsize
\newcommand\small{%
   \@setfontsize\small{8}{10}%
   \abovedisplayskip 8\p@ \@plus3\p@ \@minus4\p@
   \abovedisplayshortskip \z@ \@plus2\p@
   \belowdisplayshortskip 4\p@ \@plus2\p@ \@minus2\p@
   \def\@listi{\leftmargin\leftmargini
               \topsep 4\p@ \@plus2\p@ \@minus2\p@
               \parsep 2\p@ \@plus\p@ \@minus\p@
               \itemsep \parsep}%
   \belowdisplayskip \abovedisplayskip
}
\newcommand\footnotesize{%
   \@setfontsize\footnotesize{9}{11}%
   \abovedisplayskip 6\p@ \@plus2\p@ \@minus4\p@
   \abovedisplayshortskip \z@ \@plus\p@
   \belowdisplayshortskip 3\p@ \@plus\p@ \@minus2\p@
   \def\@listi{\leftmargin\leftmargini
               \topsep 3\p@ \@plus\p@ \@minus\p@
               \parsep 2\p@ \@plus\p@ \@minus\p@
               \itemsep \parsep}%
   \belowdisplayskip \abovedisplayskip
}
\newcommand\scriptsize{\@setfontsize\scriptsize\@viipt\@viiipt}
\newcommand\tiny{\@setfontsize\tiny\@vpt\@vipt}
\newcommand\large{\@setfontsize\large\@xipt{13}}
\newcommand\Large{\@setfontsize\Large\@xivpt{18}}
\newcommand\LARGE{\@setfontsize\LARGE\@xviipt{22}}
\newcommand\huge{\@setfontsize\huge\@xxpt{25}}
\newcommand\Huge{\@setfontsize\Huge\@xxvpt{30}}
\setlength\parindent{11pt}
%
\setlength\textwidth{38pc}
\setlength\textheight{47pc}
\setlength\topmargin{1pc}
\setlength\headheight{12\p@}
\setlength\headsep   {16\p@}
\setlength\topskip   {10\p@}
\setlength\footskip{35\p@}
\addtolength\evensidemargin{6pt}
\addtolength\oddsidemargin{6pt}
\setlength\marginparsep{11\p@}
\setlength\marginparpush{5\p@}
%
\setlength\partopsep{0pt}%2\p@ \@plus 1\p@ \@minus 1\p@}
\def\@listi{\leftmargin\leftmargini
            \parsep 0\p@% \@plus2\p@ \@minus\p@
            \topsep 8\p@ \@plus2\p@ \@minus2\p@
            \itemsep0\p@}% \@plus2\p@ \@minus\p@}
\let\@listI\@listi
\@listi
\def\@listii {\leftmargin\leftmarginii
              \labelwidth\leftmarginii
              \advance\labelwidth-\labelsep
              \topsep    0\p@% \@plus2\p@ \@minus\p@
              \parsep    0\p@% \@plus\p@  \@minus\p@
              \itemsep0\p@}
\def\@listiii{\leftmargin\leftmarginiii
              \labelwidth\leftmarginiii
              \advance\labelwidth-\labelsep
              \topsep    2\p@ \@plus\p@\@minus\p@
              \parsep    \z@
              \partopsep \p@ \@plus\z@ \@minus\p@
              \itemsep   \topsep}
\def\@listiv {\leftmargin\leftmarginiv
              \labelwidth\leftmarginiv
              \advance\labelwidth-\labelsep}
\def\@listv  {\leftmargin\leftmarginv
              \labelwidth\leftmarginv
              \advance\labelwidth-\labelsep}
\def\@listvi {\leftmargin\leftmarginvi
              \labelwidth\leftmarginvi
              \advance\labelwidth-\labelsep}
%
\def\@listI{\leftmargin\leftmargini
            \parsep 0\p@% \@plus2\p@ \@minus\p@
            \topsep 6\p@ \@plus2\p@% \@minus2\p@
            \itemsep0\p@}% \@plus2\p@ \@minus\p@}

\newenvironment{unnumlist}{\list{}{\leftmargin11\p@\itemindent-11\p@}}{\endlist}%

\newbox\abstractbox
\def\titlefont{\fontsize{17}{20}\selectfont\centering}
\def\authorfont{\fontsize{12.5}{14.5}\selectfont\centering}
\def\affilfont{\fontsize{9}{11}\selectfont\itshape\centering}
\def\datefont{\fontsize{9}{11}\selectfont}
\def\abstractfont{\fontsize{10}{12}\selectfont}
\def\keywordsfont{\fontsize{9}{11}\selectfont}
\def\historyfont{\fontsize{9}{11}\selectfont\centering}
\def\rhfont{\fontsize{9}{10}\selectfont\itshape}
\def\foliofont{\fontsize{9}{10}\selectfont}
\def\footerfont{\fontsize{8.5}{10}\selectfont}
\def\extractfont{\fontsize{9}{11}\selectfont\leftskip1pc\rightskip\leftskip}%
\def\figcaptionfont{\fontsize{9}{11}\selectfont\centering}
\def\tablecaptionfont{\fontsize{9}{11}\selectfont}
\def\tablefont{\fontsize{9}{11}\selectfont}
\def\tabnotefont{\fontsize{8.5}{10}\selectfont}
\def\extractfont{\leftskip1.5pc\rightskip\leftskip}
%%
\let\@papertype\empty
\let\@affil\empty
\let\@authoremail\empty
\let\@historydate\@empty
\let\@doi\empty
\let\@cortext\empty
\let\@keywords\empty
\let\itorauthors\empty
\def\@runningauthor{Author Name}
\def\author{\@ifnextchar[{\@@author}{\@author}}
\def\@@author[#1]#2{\gdef\@runningauthor{#1}\gdef\itorauthors{#2}}
\def\@author#1{\gdef\itorauthors{#1}}
\def\papertype#1{\gdef\@papertype{#1}}
\def\affil#1{\g@addto@macro\@affil{#1\par}}
\def\email#1{\g@addto@macro\@authoremail{#1\par}}
\def\historydate#1{\gdef\@historydate{#1}}
\def\doi#1{\gdef\@doi{#1}}\gdef\@doi{}
\def\jname#1{\gdef\@jname{#1}}\jname{International Transactions in Operational Research}
\def\societyname#1{\gdef\@societyname{#1}}\societyname{International Federation of Operational Research Societies}
\def\jvol#1{\gdef\@jvol{#1}}\jvol{xx}
\def\jnum#1{\gdef\@jnum{No.\space#1}}\jnum{xx}
\def\jyear#1{\gdef\@jyear{#1}}\jyear{\the\year}
\def\endpage#1{\gdef\@endpage{#1}}\endpage{}%
\def\firstpage#1{\gdef\@firstpage{#1}}\firstpage{1}%
\def\affmark#1{\textsuperscript{\reset@font#1}}
\long\def\keywords#1{\gdef\@keywords{#1}}
\AtBeginDocument{%
  \@ifundefined{bibsection}{\newcommand\bibsection{\section*{\refname}}}{\renewcommand\bibsection{\section*{\refname}}}
  \def\bibfont{\fontsize{9}{11}\selectfont}%
  \setlength{\bibhang}{18pt}
  \mathindent24pt%
}
\def\thanks#1{%\footnotemark
    \protected@xdef\@thanks{\@thanks
        \protect\footnotetext[\the\c@footnote]{#1}}}
\def\short@jname{Intl. Trans. in Op. Res.}
\def\slugline{{\small\centering\vspace*{-32pt}%
\short@jname\ \ifx\@jvol\@empty{XX}\else\@jvol\fi\ (\ifx\@jyear\@empty{20XX}\else\@jyear\fi) \thepage--\@endpage\par%
\ifx\@doi\@empty{DOI:\space xx.xxxx/itor.xxxxx}\else DOI:\space\@doi\fi\par}}
%%
\newenvironment{extract}{\par\addvspace{7pt plus2pt}
      \extractfont\ignorespaces\parindent0pt% 
}{%
      \par\addvspace{6pt plus2pt}}
%
\newbox\defbox%
\newdimen\defboxdimen%
\def\deflist{\@ifnextchar[{\@deflist}{\@deflist[]}}
\def\@deflist[#1]{%
  \setbox\defbox\hbox{#1:\quad}%
  \defboxdimen\wd\defbox%
  \def\tempa{#1}%
  \par\addvspace{6pt plus2pt minus2pt}%
  \setlength\parindent{0pt}%
  \def\deftitle##1{{\noindent##1}\par}%
  \ifx\tempa\@empty
    \def\listitem##1##2{\@hangfrom{##1\quad}##2\par}
  \else%
    \def\listitem##1##2{\@hangfrom{\hbox to \defboxdimen{\hss##1\quad}}{##2\par}}%%
  \fi%
}
%
\def\enddeflist{\par\addvspace{6pt plus2pt minus2pt}}
%
\setlength\lineskip{1\p@}
\setlength\normallineskip{1\p@}
\renewcommand\baselinestretch{}
\setlength\parskip{0\p@}
\@lowpenalty   51
\@medpenalty  151
\@highpenalty 301
\setcounter{topnumber}{5}
\renewcommand\topfraction{.9}
\setcounter{bottomnumber}{5}
\renewcommand\bottomfraction{.9}
\setcounter{totalnumber}{5}
\renewcommand\textfraction{.09}
\renewcommand\floatpagefraction{.901}
\setcounter{dbltopnumber}{5}
\renewcommand\dbltopfraction{.9}
\renewcommand\dblfloatpagefraction{.99}%.901}

\def\ps@plain{\let\@mkboth\@gobbletwo%
       \def\@oddfoot{\parbox{\textwidth}{\footerfont%
           \copyright\ \the\year\ %The Authors.\par
           \@jname\ \copyright\ \the\year\ \@societyname}}%
       \def\@oddhead{\hfill\parbox{90pt}{\centering\vspace*{-12pt}%
           \rule{88pt}{.5pt}\par\vspace*{-11pt}\rule{88pt}{.5pt}\par
           \fontsize{10}{12}\selectfont\bfseries INTERNATIONAL\par TRANSACTIONS\par IN OPERATIONAL\par RESEARCH\par\vspace*{-6pt}
           \rule{88pt}{.5pt}\par\vspace*{-10pt}\rule{88pt}{.5pt}\par}}
       \def\@evenhead{}}%

\def\ps@headings{%
    \let\@oddfoot\@empty\let\@evenfoot\@empty
    \def\@evenhead{{\foliofont\thepage}\hfil{\rhfont\@runningauthor\space/\space\short@jname\space\@jvol\ (\@jyear) \@firstpage--\@endpage}\hfil}%
    \def\@oddhead{\hfil{{\rhfont\@runningauthor\space/\space\short@jname\@jvol\ (\@jyear) \@firstpage--\@endpage}}\hfil{\foliofont\thepage}}%
    \def\@evenfoot{\parbox{\textwidth}{\footerfont\raggedleft%
         \copyright\ \the\year\ %The Authors.\par%
         \@jname\ \copyright\ \the\year\ \@societyname}}%
    \def\@oddfoot{\parbox{\textwidth}{\footerfont%
         \copyright\ \the\year\ %The Authors.\par
         \@jname\ \copyright\ \the\year\ \@societyname}}%
    \let\@mkboth\markboth
    \def\chaptermark##1{\markboth{##1}{##1}}%
    \def\sectionmark##1{\markright{##1}}}

\newcommand\maketitle{\par
  \begingroup
    \renewcommand\thefootnote{\@fnsymbol\c@footnote}%
    \def\@makefnmark{\rlap{\@textsuperscript{\normalfont\@thefnmark}}}%
    \long\def\@makefntext##1{\parindent 0em\noindent{\@textsuperscript{\normalfont\@thefnmark}}##1}%
    \if@twocolumn
      \ifnum \col@number=\@ne
        \@maketitle
      \else
        \twocolumn[\@maketitle]%
      \fi
    \else
      \newpage
      \global\@topnum\z@   % Prevents figures from going at top of page.
      \@maketitle
    \fi    
  \endgroup
  \setcounter{footnote}{0}%
  \global\let\thanks\relax
  \global\let\maketitle\relax
  \global\let\@maketitle\relax
  \global\let\@thanks\@empty
  \global\let\itorauthors\@empty
  \global\let\@date\@empty
  \global\let\@title\@empty
  \global\let\title\relax
  \global\let\author\relax
  \global\let\date\relax
  \global\let\and\relax
}

\def\@maketitle{%
  \newpage
  \null
  \vskip 2em%
  \let\footnote\thanks
  \thispagestyle{plain}\@thanks%
  \immediate\write\@mainaux{\string\firstpage{\thepage}}
  \slugline\vskip33pt%
  \ifx\title\@empty\else{\titlefont\@title\vphantom{pg}\par\vskip12pt}\fi%
  \ifx\itorauthors\@empty\else{\authorfont\itorauthors\par\vskip7pt}\fi%
  \ifx\@affil\@empty\else{\affilfont\@affil\par}\fi%
  \ifx\@authoremail\@empty\else{\affilfont E-mail:\space\@authoremail\par\vskip10pt}\fi%
  \ifx\@historydate\@empty\else{{\historyfont\@historydate\par}}\fi%
  %
  \ifvoid\abstractbox%
     \ifx\@keywords\@empty\else\noindent\rule{\textwidth}{.5pt}\par\fi%
  \else%
     {\unvbox\abstractbox\par\vskip10pt}%
  \fi%
  \ifx\@keywords\@empty\else{\keywordsfont\noindent{\itshape Keywords:\space}\@keywords\par}\fi%
  \noindent\rule{\textwidth}{.5pt}\par%
  %
  \par\vskip 1.5em}

\setcounter{secnumdepth}{3}
\newcounter {part}
\newcounter {section}
\newcounter {subsection}[section]
\newcounter {subsubsection}[subsection]
\newcounter {paragraph}[subsubsection]
\newcounter {subparagraph}[paragraph]
\renewcommand \thepart {\@Roman\c@part}
\renewcommand \thesection {\@arabic\c@section}
\renewcommand\thesubsection   {\thesection.\@arabic\c@subsection}
\renewcommand\thesubsubsection{\thesubsection .\@arabic\c@subsubsection}
\renewcommand\theparagraph    {\thesubsubsection.\@arabic\c@paragraph}
\renewcommand\thesubparagraph {\theparagraph.\@arabic\c@subparagraph}
\newcommand\part{%
   \if@noskipsec \leavevmode \fi
   \par
   \addvspace{4ex}%
   \@afterindentfalse
   \secdef\@part\@spart}

\def\@part[#1]#2{%
    \ifnum \c@secnumdepth >\m@ne
      \refstepcounter{part}%
      \addcontentsline{toc}{part}{\thepart\hspace{1em}#1}%
    \else
      \addcontentsline{toc}{part}{#1}%
    \fi
    {\parindent \z@ \raggedright
     \interlinepenalty \@M
     \normalfont
     \ifnum \c@secnumdepth >\m@ne
       \Large\bfseries \partname\nobreakspace\thepart
       \par\nobreak
     \fi
     \huge \bfseries #2%
     \markboth{}{}\par}%
    \nobreak
    \vskip 3ex
    \@afterheading}
\def\@spart#1{%
    {\parindent \z@ \raggedright
     \interlinepenalty \@M
     \normalfont
     \huge \bfseries #1\par}%
     \nobreak
     \vskip 3ex
     \@afterheading}

\newcommand\section{\@startsection {section}{1}{\z@}%
                                   {-25pt \@plus -2pt \@minus -.2pt}%
                                   {13pt}%
                                   {\normalfont\large\bfseries}}
\newcommand\subsection{\@startsection{subsection}{2}{\z@}%
                                     {-26pt \@plus -2pt \@minus -.2pt}%
                                     {12.5pt}%
                                     {\normalfont\large\itshape}}
\newcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
                                     {-19pt \@plus -2pt \@minus -.2pt}%
                                     {.1pt}%
                                     {\normalfont\large\itshape}}
\newcommand\paragraph{\@startsection{paragraph}{4}{\z@}%
                                    {-19pt \@plus -2pt \@minus -.2pt}%
                                    {-1em}%
                                    {\normalfont\itshape}}
\newcommand\subparagraph{\@startsection{subparagraph}{5}{\parindent}%
                                       {-19pt \@plus -2pt \@minus -.2pt}%
                                       {-1em}%
                                      {\normalfont\normalsize}}
%%%% Section macro modified %%%%%%%% Aptara
\def\@seccntformat#1{\csname the#1\endcsname.\hskip5pt}
%
\def\@sect#1#2#3#4#5#6[#7]#8{%
  \ifnum #2>\c@secnumdepth
    \let\@svsec\@empty
  \else
    \refstepcounter{#1}%
    \protected@edef\@svsec{\@seccntformat{#1}\relax}%
  \fi
  \@tempskipa #5\relax
  \ifdim \@tempskipa>\z@
    \begingroup
      #6\relax%{%
     \ifnum#2=1%
       \ifx\appendix@start\YES%
          \@hangfrom{\hskip #3\relax}%
            {\interlinepenalty \@M #8\@@par}%
       \else%
          \@hangfrom{\hskip #3\relax\@svsec}%
            {\interlinepenalty \@M #8\@@par}%
       \fi%     
     \else%
        \@hangfrom{\hskip #3\relax\@svsec}%
          {\interlinepenalty \@M #8\@@par}%
     \fi%     
    \endgroup
    \csname #1mark\endcsname{#7}%
    \addcontentsline{toc}{#1}{%
      \ifnum #2>\c@secnumdepth \else
        \protect\numberline{\csname the#1\endcsname}%
      \fi
      #7}%
  \else
    \def\@svsechd{%
      #6{\hskip #3\relax
      \@svsec #8.}%
      \csname #1mark\endcsname{#7}%
      \addcontentsline{toc}{#1}{%
        \ifnum #2>\c@secnumdepth \else
          \protect\numberline{\csname the#1\endcsname}%
        \fi
        #7}}%
  \fi
  \@xsect{#5}}
%
\if@twocolumn
  \setlength\leftmargini  {2em}
\else
  \setlength\leftmargini  {1.2em}
\fi
\leftmargin  \leftmargini
\setlength\leftmarginii  {2em}
\setlength\leftmarginiii {1.87em}
\setlength\leftmarginiv  {1.7em}
\if@twocolumn
  \setlength\leftmarginv  {.5em}
  \setlength\leftmarginvi {.5em}
\else
  \setlength\leftmarginv  {1em}
  \setlength\leftmarginvi {1em}
\fi
\setlength  \labelsep  {.5em}
\setlength  \labelwidth{\leftmargini}
\addtolength\labelwidth{-\labelsep}
\@beginparpenalty -\@lowpenalty
\@endparpenalty   -\@lowpenalty
\@itempenalty     -\@lowpenalty
\renewcommand\theenumi{\@arabic\c@enumi}
\renewcommand\theenumii{\@alph\c@enumii}
\renewcommand\theenumiii{\@roman\c@enumiii}
\renewcommand\theenumiv{\@Alph\c@enumiv}
\newcommand\labelenumi{\theenumi.}
\newcommand\labelenumii{(\theenumii)}
\newcommand\labelenumiii{\theenumiii.}
\newcommand\labelenumiv{\theenumiv.}
\renewcommand\p@enumii{\theenumi}
\renewcommand\p@enumiii{\theenumi(\theenumii)}
\renewcommand\p@enumiv{\p@enumiii\theenumiii}
\newcommand\labelitemi{\textbullet}
\newcommand\labelitemii{\normalfont\bfseries \textemdash}
\newcommand\labelitemiii{\textasteriskcentered}
\newcommand\labelitemiv{\textperiodcentered}
\newenvironment{description}
               {\list{}{\labelwidth\z@ \itemindent-\leftmargin
                        \let\makelabel\descriptionlabel}}
               {\endlist}
\newcommand*\descriptionlabel[1]{\hspace\labelsep
                                \normalfont\bfseries #1}
\newenvironment{abstract}{%
   \global\setbox\abstractbox\vbox\bgroup\parindent\z@\vskip30pt%
   \rule{\textwidth}{.5pt}\par%
   {\bfseries\abstractname\par\vskip9pt}%
     \abstractfont}
     {\par\egroup}%

\newenvironment{verse}
               {\let\\\@centercr
                \list{}{\itemsep      \z@
                        \itemindent   -1.5em%
                        \listparindent\itemindent
                        \rightmargin  \leftmargin
                        \advance\leftmargin 1.5em}%
                \item\relax}
               {\endlist}
\newenvironment{quotation}
               {\list{}{\listparindent 1.5em%
                        \itemindent    \listparindent
                        \rightmargin   \leftmargin
                        \parsep        \z@ \@plus\p@}%
                \item\relax}
               {\endlist}
\newenvironment{quote}
               {\list{}{\rightmargin\leftmargin}%
                \item\relax}
               {\endlist}
%
\setlength\arraycolsep{5\p@}
\setlength\tabcolsep{6\p@}
\setlength{\skip\footins}{20\p@ \@plus 8\p@ \@minus 8\p@}%
\setlength\arrayrulewidth{.4\p@}
\setlength\doublerulesep{2\p@}
\setlength\tabbingsep{\labelsep}
\skip\@mpfootins = \skip\footins
\setlength\fboxsep{3\p@}
\setlength\fboxrule{.4\p@}
\renewcommand \theequation {\@arabic\c@equation}
\newcounter{figure}
\renewcommand \thefigure {\@arabic\c@figure}
\def\fps@figure{tbp}
\def\ftype@figure{1}
\def\ext@figure{lof}
\def\fnum@figure{\figurename\nobreakspace\thefigure}
\newenvironment{figure}[1][tbp]
               {\@float{figure}[#1]\vskip3pt}
               {\end@float}
\newenvironment{figure*}[1][tbp]
               {\@dblfloat{figure}[#1]\vskip3pt}
               {\end@dblfloat}
\newcounter{table}
\renewcommand\thetable{\@arabic\c@table}
\def\fps@table{tbp}
\def\ftype@table{2}
\def\ext@table{lot}
\def\fnum@table{\tablename\nobreakspace\thetable}
\newenvironment{table}[1][tbp]
               {\@float{table}[#1]\process@tablenotes}
               {\tabnote\PrintTableNotes\endtabnote\end@float}%
\newenvironment{table*}[1][tbp]
               {\@dblfloat{table}[#1]\process@tablenotes}
               {\tabnote\PrintTableNotes\endtabnote\end@dblfloat}
\AtBeginDocument{\@ifpackageloaded{rotating}{%
   \renewenvironment{sidewaystable}{\@rotfloat{table}\process@tablenotes}{\tabnote\PrintTableNotes\endtabnote\end@rotfloat}%
   \renewenvironment{sidewaystable*}{\@rotdblfloat{table}\process@tablenotes}{\tabnote\PrintTableNotes\endtabnote\end@rotdblfloat}%
}{}}

%%== \tch[number-of-column][alignment(c,l,r)]{text}
\newcommand\tch[3]{\multicolumn{#1}{@{}#2@{}}%
   {\begin{tabular}[b]{#2@{}}%
    \ignorespaces#3\unskip
    \end{tabular}}}

\newcommand\process@tablenotes{%
    \def\tablenote##1{\g@addto@macro\PrintTableNotes{\footnotesize##1\par}}
    \gdef\PrintTableNotes{}%
}
\def\tabnotemark#1{\textsuperscript{\smash{{#1}}}}

\def\tabular{\tablefont\let\@halignto\@empty\@tabular}
\@namedef{tabular*}#1{\tablefont%
 \setlength\dimen@{#1}%
   \edef\@halignto{to\the\dimen@}\@tabular}

\newenvironment{tabnote}{%
  \par\addvspace{-5pt}\,%
  \tabnotefont
}{%
  \par}
\def\hline{%
  \noalign{\ifnum0=`}\fi\vskip3pt
      \hrule \@height \arrayrulewidth\vskip3pt
      \futurelet \reserved@a\@xhline}

\newlength\abovecaptionskip
\newlength\belowcaptionskip
\setlength\abovecaptionskip{12\p@}
\setlength\belowcaptionskip{3.5\p@}
\def\FigName{figure}
\long\def\@makecaption#1#2{%
  \ifx\FigName\@captype%
    \vskip\abovecaptionskip
      {\figcaptionfont{#1.}\hskip5pt#2\par}%
  \else%
   {\tablecaptionfont #1\par#2\par}%
   \vskip\belowcaptionskip
  \fi
  }
\DeclareOldFontCommand{\rm}{\normalfont\rmfamily}{\mathrm}
\DeclareOldFontCommand{\sf}{\normalfont\sffamily}{\mathsf}
\DeclareOldFontCommand{\tt}{\normalfont\ttfamily}{\mathtt}
\DeclareOldFontCommand{\bf}{\normalfont\bfseries}{\mathbf}
\DeclareOldFontCommand{\it}{\normalfont\itshape}{\mathit}
\DeclareOldFontCommand{\sl}{\normalfont\slshape}{\@nomath\sl}
\DeclareOldFontCommand{\sc}{\normalfont\scshape}{\@nomath\sc}
\DeclareRobustCommand*\cal{\@fontswitch\relax\mathcal}
\DeclareRobustCommand*\mit{\@fontswitch\relax\mathnormal}
\newcommand\@pnumwidth{1.55em}
\newcommand\@tocrmarg{2.55em}
\newcommand\@dotsep{4.5}
\setcounter{tocdepth}{3}
\newcommand\tableofcontents{%
    \section*{\contentsname
        \@mkboth{%
           \MakeUppercase\contentsname}{\MakeUppercase\contentsname}}%
    \@starttoc{toc}%
    }
\newcommand*\l@part[2]{%
  \ifnum \c@tocdepth >-2\relax
    \addpenalty\@secpenalty
    \addvspace{2.25em \@plus\p@}%
    \setlength\@tempdima{3em}%
    \begingroup
      \parindent \z@ \rightskip \@pnumwidth
      \parfillskip -\@pnumwidth
      {\leavevmode
       \large \bfseries #1\hfil \hb@xt@\@pnumwidth{\hss #2}}\par
       \nobreak
       \if@compatibility
         \global\@nobreaktrue
         \everypar{\global\@nobreakfalse\everypar{}}%
      \fi
    \endgroup
  \fi}
\newcommand*\l@section[2]{%
  \ifnum \c@tocdepth >\z@
    \addpenalty\@secpenalty
    \addvspace{1.0em \@plus\p@}%
    \setlength\@tempdima{1.5em}%
    \begingroup
      \parindent \z@ \rightskip \@pnumwidth
      \parfillskip -\@pnumwidth
      \leavevmode \bfseries
      \advance\leftskip\@tempdima
      \hskip -\leftskip
      #1\nobreak\hfil \nobreak\hb@xt@\@pnumwidth{\hss #2}\par
    \endgroup
  \fi}
\newcommand*\l@subsection{\@dottedtocline{2}{1.5em}{2.3em}}
\newcommand*\l@subsubsection{\@dottedtocline{3}{3.8em}{3.2em}}
\newcommand*\l@paragraph{\@dottedtocline{4}{7.0em}{4.1em}}
\newcommand*\l@subparagraph{\@dottedtocline{5}{10em}{5em}}
\newcommand\listoffigures{%
    \section*{\listfigurename}%
      \@mkboth{\MakeUppercase\listfigurename}%
              {\MakeUppercase\listfigurename}%
    \@starttoc{lof}%
    }
\newcommand*\l@figure{\@dottedtocline{1}{1.5em}{2.3em}}
\newcommand\listoftables{%
    \section*{\listtablename}%
      \@mkboth{%
          \MakeUppercase\listtablename}%
         {\MakeUppercase\listtablename}%
    \@starttoc{lot}%
    }
\let\l@table\l@figure
\newdimen\bibindent
\setlength\bibindent{1.5em}
\newenvironment{thebibliography}[1]
     {\bibfont\section*{\refname}%
      %% \@mkboth{\MakeUppercase\refname}{\MakeUppercase\refname}%
      \list{\@biblabel{\@arabic\c@enumiv}}%
           {\settowidth\labelwidth{\@biblabel{#1}}%
            \leftmargin\labelwidth
            \advance\leftmargin\labelsep
            \@openbib@code
            \usecounter{enumiv}%
            \let\p@enumiv\@empty
            \renewcommand\theenumiv{\@arabic\c@enumiv}}%
      \sloppy
      \clubpenalty4000
      \@clubpenalty \clubpenalty
      \widowpenalty4000%
      \sfcode`\.\@m}
     {\def\@noitemerr
       {\@latex@warning{Empty `thebibliography' environment}}%
      \endlist}
\newcommand\newblock{\hskip .11em\@plus.33em\@minus.07em}
\let\@openbib@code\@empty
\newenvironment{theindex}
               {\if@twocolumn
                  \@restonecolfalse
                \else
                  \@restonecoltrue
                \fi
                \twocolumn[\section*{\indexname}]%
                \@mkboth{\MakeUppercase\indexname}%
                        {\MakeUppercase\indexname}%
                \thispagestyle{plain}\parindent\z@
                \parskip\z@ \@plus .3\p@\relax
                \columnseprule \z@
                \columnsep 35\p@
                \let\item\@idxitem}
               {\if@restonecol\onecolumn\else\clearpage\fi}
\newcommand\@idxitem{\par\hangindent 40\p@}
\newcommand\subitem{\@idxitem \hspace*{20\p@}}
\newcommand\subsubitem{\@idxitem \hspace*{30\p@}}
\newcommand\indexspace{\par \vskip 10\p@ \@plus5\p@ \@minus3\p@\relax}
\renewcommand\footnoterule{%
  \kern-6\p@
  \hrule\@width0pt
  \kern6\p@}
\newcommand\@makefntext[1]{%
    \parindent 0em%
    \noindent
    {\@makefnmark}#1}%\hb@xt@1.8em\hss
\newcommand\contentsname{Contents}
\newcommand\listfigurename{List of Figures}
\newcommand\listtablename{List of Tables}
\newcommand\refname{References}
\newcommand\indexname{Index}
\newcommand\figurename{Fig.}
\newcommand\tablename{Table}
\newcommand\partname{Part}
\newcommand\appendixname{Appendix}
\newcommand\abstractname{Abstract}
\def\today{\ifcase\month\or
  January\or February\or March\or April\or May\or June\or
  July\or August\or September\or October\or November\or December\fi
  \space\number\day, \number\year}
\setlength\columnsep{10\p@}
\setlength\columnseprule{0\p@}

\def\withinappsection{no}%
\gdef\appendix@start{no}%
\gdef\YES{yes}%
\gdef\NO{no}%
\newcommand\appsection{\gdef\withinappsection{yes}\appendix\@startsection {section}{1}{\z@}%
           {-25pt \@plus -2pt \@minus -.2pt}%
           {13pt}% \@plus 6\p@ \@minus 3\p@
           {\normalfont\large\bfseries}}

\newcommand\appendix{\par%
  \ifx\appendix@start\YES\else\setcounter{section}{0}\fi%
  \setcounter{subsection}{0}%
  \setcounter{equation}{0}%
  \setcounter{table}{0}%
  \setcounter{figure}{0}%
  \gdef\thefigure{\@Alph\c@section\arabic{figure}}%
  \gdef\thetable{\@Alph\c@section\arabic{table}}%
  \gdef\thesection{\@Alph\c@section}%
  \gdef\theHsection{\Alph{section}}%
  \gdef\theequation{\@Alph\c@section\arabic{equation}}%
  \gdef\appendix@start{yes}
  %% \addtocontents{toc}{\string\let\string\numberline\string\tmptocnumberline}{}{}%
}

\def\enddocument{%
   \let\AtEndDocument\@firstofone
   \@enddocumenthook
   \@checkend{document}%
   \clearpage
   \begingroup
     \if@filesw
       \advance\c@page\m@ne
       \immediate\write\@mainaux{\string\endpage{\thepage}}%
       \immediate\closeout\@mainaux
       \let\@setckpt\@gobbletwo
       \let\@newl@bel\@testdef
       \@tempswafalse
       \makeatletter \input\jobname.aux
     \fi
     \@dofilelist
     \ifdim \font@submax >\fontsubfuzz\relax
       \@font@warning{Size substitutions with differences\MessageBreak
                  up to \font@submax\space have occurred.\@gobbletwo}%
     \fi
     \@defaultsubs
     \@refundefined
     \if@filesw
       \ifx \@multiplelabels \relax
         \if@tempswa
           \@latex@warning@no@line{Label(s) may have changed.
               Rerun to get cross-references right}%
         \fi
       \else
         \@multiplelabels
       \fi
     \fi
   \endgroup
   \deadcycles\z@\@@end}

\RequirePackage{ifpdf}%
\ifpdf
\pdfpagewidth=8.5in
\pdfpageheight=11in
\fi
%%
%% ============================
\pagestyle{headings}
\pagenumbering{arabic}
\sloppy
\frenchspacing
\flushbottom
\hbadness=10000
\vbadness=10000
%% ============================
\endinput
%%
%% End of file `itor.cls'.
