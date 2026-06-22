==============
 Introduction
==============

A program suite for doing CBGM.

----------------------------------------------------------------------------
Basic Terms and Procedures of the Coherence-Based Genealogical Method (CBGM)
----------------------------------------------------------------------------

The Coherence-Based Genealogical Method, developed by Gerd Mink at the 
Institut für Neutestamentliche Textforschung (INTF) in Münster, aims at a 
scientifically founded reconstruction of the initial text (*Ausgangstext*) of 
the New Testament tradition, i.e. a hypothesis about the text from which the 
manuscript transmission started. The fundamental problem posed by the nature 
of the New Testament manuscript tradition is known as contamination, the 
mutual influence of different strands of transmission on each other. 
Contamination renders the application of conventional stemmatics impossible, 
and the New Testament manuscript tradition is known to be highly contaminated. 
The CBGM, however, offers a cure for contamination, thanks to three essential 
principles distinguishing it from conventional stemmatics. 

1) The CBGM does not study the genealogy of manuscripts but of the texts 
carried by the manuscripts, the textual witnesses. **The text is the 
witness.**
2) The CBGM does not deduce the genealogy of textual witnesses from common 
errors but from the genealogy of the variants by which the witnesses either 
agree or differ.
3) The CBGM is based on the awareness that, due to contamination, two 
witnesses when compared with each other both feature earlier and later, 
prior and posterior variants. As a rule, one of the two witnesses contains 
more prior variants than the other and is thus regarded as the *potential 
ancestor* of the other. At a lower number of passages, however, the descendant 
will contain prior variants, and this fact is taken into account 
systematically.

The CBGM was developed in the context of the *Editio Critica Maior – Novum 
Testamentum Graecum* (ECM). 

.. pic: jpg
   :file: ECM01.jpg
   :align: center
   :alt: Fig. 1: ECM of the Acts of the Apostles
   
The application requires a comprehensive, well-structured critical apparatus 
meeting the ECM standard. For each of the manuscripts included there is one 
entry at each variant passage. The apparatus of Acts, for example, contains 
all variants of 183 Greek witnesses at more than 7,000 variant passages. 

The CBGM proceeds from the genealogy of variants to the genealogy of the 
witnesses containing the variants. If the editors judge a variant *b* as 
posterior to a variant *a*, they also make a statement about the relationship 
between the witnesses of *a* and *b* at one passage. Hence the following 
principle of the CBGM:

**A hypothesis about genealogical relationships between the states of a 
text as preserved in the manuscripts has to rest upon the genealogical 
relationships between the variants they exhibit. Therefore a systematic 
assessment of the genealogy of these variants (displayed as local stemmata) 
is a necessary requirement for examining the genealogy of textual witnesses.**

.. pic: jpg
   :file: LocStem01.jpg
   :align: left
   :alt: Fig. 2: A local stemma of variants

The relationship between two witnesses as compared at one variant passage 
can take four forms.
1) They are equal (01 and 02 in fig. 2).
2) They differ and have an ancestor-descendant relationship (03 and 04 
are descendants of 01 and 02 in fig. 2).
3) They differ and are posterior to other witnesses but are not directly 
related (03 and 04 in fig. 2).
4) They differ and the relationship is unclear because the source of the 
variant in one of the compared witnesses is not defined (as for *d* in 05).

Having constructed local stemmata for each variant passage we are able 
to say in how many instances witness X has the prior variant as compared 
with witness Y at the places where they differ. As we are dealing with a 
contaminated tradition, there will also be a number of instances where 
Y has the prior variant. Finally there will be a number of unclear cases 
where the variants of X and Y are not directly related or it has to be 
left open which is the prior one. These numbers are tabulated in lists 
of relatives for each of the witnesses included in the apparatus.

.. pic:jpg
   :file: Relatives01.jpg
   :align: left
   :alt: Fig. 3: Relatives list of witness 01 in Acts (Phase 4)

The structure of the relatives list is explained by the *Short Guide* on 
the website <https://ntg.uni-muenster.de/acts/ph4/>. Here we focus on what 
is essential for this brief introduction.
The first line above the table identifies the witness the list of relatives 
refers to: 01 as W(itness) 1 supporting variant c at the given passage and 
being cited at a total of 7,392 variant passages in Acts. For each of the 
compared witnesses (under W2 in the table) the table shows 
1) how many passages W1 and W2 are equal (Eq);
2) whether W2 is a potential ancestor or descendant of W1 (W1<W2 larger 
or smaller than W1>W2);
3) how many passages W1 and W2 are not directly related (NoRel);
4) how many passages the relationship between W1 and W2 is unclear 
because the source of the variant in W1 or in W2 is not defined (Uncl).

The table is organized by the percentages of agreement (Perc) by default 
(and can be reorganized according to the user). These percentages indicate 
the degree of *pre-genealogical coherence* of the witnesses under comparison, 
while their *genealogical coherence* is shown by the figures under W1<W2 and 
W1>W2. As mentioned above, W2 is considered a *potential ancestor* of W1, 
if W1<W2 is larger than W1>W2. In this case a ranking number corresponding 
to the percentage of agreement (Perc) appears under NR. According to fig. 
3, A is the first, 81 the fifth potential ancestor of 01.
The figures under W1<W2 and W1>W2 show the relative strength of the 
*textual flow* leading from prior variants in W1 to posterior variants in W2.

All diagrams in *Coherence and Textual Flow* displayed below the local 
stemma of the selected passage derive from tables like the one in fig. 3. 
The ECM editors use the textual flow diagrams of the module *Coherence in 
Attestations* as a starting point when assessing the quality and coherence 
of attestations. The textual flow diagrams show the witnesses with a range 
of potential ancestors, which is defined by the connectivity attributed to 
a variant by the user[1]_.  The potential ancestors within the connectivity 
range are either part of the same attestation or they support another variant. 
In our example all the potential ancestors outside the attestation of c 
support a. This is a strong argument for assessing *a* as prior to *c*.

.. pic: jpg
   :file: Coherence01.jpg 
   :align: left
   :alt: Fig. 4: Textual flow diagram for Acts 3:13/8c with default parameters
  
The term *potential ancestor* was coined in view of the final procedure 
of the CBGM, the construction of the *global stemma*. A global stemma will 
be composed of *optimal substemmata* for which only stemmatic ancestors 
are used. Stemmatic ancestors are those which are *necessary* for 
explaining the text of a witness. The text of a witness is regarded 
as explained if it can be deduced completely by agreement with or 
posteriority to the variants in the ancestors. 

In the context of the CBGM the term stemma is restricted to the local 
stemma of variants and the global stemma, the final account of the 
genealogy of all witnesses that are necessary for explaining the 
development of the text from its earliest to its latest incarnations. 
By contrast, diagrams dealing with witnesses and their potential ancestors 
are called *textual flow diagrams* or TFDs.

The construction of the global stemma is work in progress. There are two 
CBGM modules geared towards the global stemma: *Optimal Substemma* (OS) and 
*Minimum Set Cover* (MSC). OS checks a range of up to 15 potential 
ancestors for optimal combinations to explain the text of a witness. 
More than 15 and the Webserver may become overstrained. MSC reaches out 
to a larger number of potential ancestors but does not check all possible 
combinations in a given range. So again, the result is only an approximation 
to an optimal substemma. An optimal result would only be yielded by a method 
that includes all combinations of all potential ancestors. In the near 
future we hope to be able to find help with developing OS software for 
utilizing a HPC cluster.

References

Novum Testamentum Graecum – Editio Critica Maior, ed. by the Institute for 
New Testament Textual Research, Münster.

Vol. III Acts of the Apostles, ed. Holger Strutwolf, Georg Gäbel, 
Annette Hüffmeier, Gerd Mink, and Klaus Wachtel. Part 1: Text, Part 2: 
Supplementary Material, Part 3: Studies, Stuttgart: 
German Bible Society 2017. ISBN 978-3-438-05614-6

Vol. IV Catholic Letters, ed. Barbara Aland, Kurt Aland†, Gerd Mink, 
Holger Strutwolf, and Klaus Wachtel. Part 1 Text, Part 2 Supplementary 
Material, 2nd revised edition, Stuttgart 2013, ISBN 978-3-438-05606-1 
and 978-3-438-05607-8.

Gerd Mink: The Coherence-Based Genealogical Method (CBGM), Introductory 
Presentation. <http://egora.uni-muenster.de/intf/service/downloads_en.shtml>

Short Bibliography on the CBGM
<http://egora.uni-muenster.de/intf/projekte/gsm_lit_en.shtml>



The program suite consists of:

#. a :mod:`web client <client>`,
#. an :mod:`API server <server>`, and
#. a set of :mod:`scripts` to manipulate the CBGM database.

.. pic:: uml
   :caption: Overview of the program suite

   skinparam backgroundColor transparent

   component "Web Client" as client
   note left of client: javascript

   component "API Server" as api
   note left of api: python

   component "Scripts" as scripts
   note right of scripts: python

   database "Database" as db
   note left of db: postgres

   client --> api
   api --> db
   scripts --> db
   api -[hidden]> scripts

The web client runs in the browser.

The API server can manage multiple databases.
Each book and phase gets its own database.

The scripts can be run manually on the VM to
manage the whole :ref:`CBGM process <cbgm>`, that is:

- importing new books,
- doing the CBGM (passing from one phase to the next),
- and eventually updating the apparatus.


Links
=====

The application is online at: http://ntg.uni-muenster.de/acts/ph4/

The source code is online at: https://github.com/scdh/intf-cbgm/

An introductory presentation to the CBGM: https://www.uni-muenster.de/INTF/cbgm_presentation/download.html

Developer 2016 - 2020: Marcello Perathoner <marcello.perathoner@uni-koeln.de>

.. [1] A variant is connective if it is unlikely that it emerged multiple 
times accidentally or via contamination. Accidental emergence is likely in 
witnesses that are not closely related if, for example, the same common 
expression appears in place of an unusual one. The connectivity of a variant 
is determined (a) by high degrees of agreement between its witnesses and 
(b) by the linguistic quality of the variant. As a rule, relationships 
between potential ancestors with ranking numbers up to 5 may be considered 
genealogically significant. Like in fig. 4, the respective connectivity 
parameter 5 often leads to a textual flow diagram with several small 
coherent groupings whose potential ancestors are outside the same attestation. 
In our example these ancestors support variant *a*.