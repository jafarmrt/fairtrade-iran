# Sources, editorial decisions and open points

What the texts in this package are based on, the choices made while writing them, and what still needs checking
by the House. Written November 2026 (Aban 1405).

## Sources

| Source | Used for |
| --- | --- |
| «نگاهی به خانه تجارت عادلانه ایران» (booklet, Shahrivar 1405, .docx) | What fair trade is, the history of WFTO, the ten principles with practical examples, the history of the House, vision, mission, membership benefits, the producer self-assessment (appendix 4) and the facilitator questionnaire (appendix 6) |
| «معرفی خانه تجارت عادلانه و مؤسسین» (PDF) | Vision, mission, operational goals, short descriptions of each founder, working groups |
| fairtradeiran Catalog 2 (English PDF) | Full profiles of the founding groups (years, numbers, websites, Instagram pages), the House's e-mail and Telegram |
| Governance document v2 (سند ارکان، Mehr 1405), as already built into the site | Membership types, admission steps, bodies of the House, complaints |
| Brand guide («تجارت عادلانه-1.pdf») | Checked against the site: colours and fonts already match (see below) |
| The repository's earlier seed texts | Legal pages (privacy, terms, returns), membership page, e-mails and SMS texts, kept and moved into this package |
| Public sources on WFTO (wfto.com, general references) | Checking dates in the WFTO history (1958, 1964, 1989, 1998, 2008, 2011) and the secretariat in Culemborg |

The founders' own websites (haftdast.com, teedacraft.com, mehrbaf.com, parvandboom.com, ormuz.ir, lenaland.ir) did
not respond from outside Iran while this was written, and their Instagram pages need a login, so they could not be
used to cross-check. papital.gallery now redirects to papital.store (Papital's European shop).

## Editorial decisions

1. **The Foundation for Entrepreneurship Development of Women and Youth (بنیاد توسعه کارآفرینی زنان و جوانان) is
   not a founding member.** It is removed from every text (About page, founders list, member directory). On sites
   that already have it, the import takes away its founding-member mark, takes it off the home page and hides it
   from the members page (`withdrawn` in `members.yaml`); `checks.yaml` makes every import report any remaining
   mention. The About page now says "seven producer groups and one capacity-building organisation, with two individuals".
2. **Chagerd (چاگرد) is kept as a founding member.** The booklet (Shahrivar 1405) lists it among the seven producer
   groups, but the introduction PDF and the English catalogue (eight groups) do not mention it. Its profile is limited
   to "products made by Baluch women" because no other information was available. **Please confirm** whether Chagerd
   is still a founding member; if not, move it to `withdrawn` in `members.yaml`.
3. **Names follow the groups' own spelling in English:** Ormuz (not Armoz; the web address stays /members/armoz/),
   Teeda Craft, Parvandboom, Papital Gallery, Lena Art Group, Haftdast House, Mehrbaf.
4. **Years:** the catalogue gives Gregorian years. Persian texts give the matching Iranian year (2019 → ۱۳۹۸,
   2012 → ۱۳۹۱, July 2012 → تیر ۱۳۹۱, 2017 → ۱۳۹۶, 2022 → ۱۴۰۱, 2015 → ۱۳۹۴, 2018 → ۱۳۹۷, 2021 → ۱۴۰۰). Where a
   Gregorian year spans two Iranian years, the later one was chosen; please check.
5. **Membership model:** the booklet's appendix 3 describes four membership levels (همراه، در حال گذار، تأییدشده،
   پیشرو). The governance document (v2, Mehr 1405, newer) uses trial and full membership, and the site follows it.
   The four levels are not shown on the site.
6. **Application form:** the booklet's producer questionnaire has about 60 questions. The form asks the ones that
   decide admission under each principle (wages, child labour, discrimination, safety, environment and so on);
   the full self-assessment is for the commission's evaluation. Appendix 5 (shops and sellers) is not used: the
   governance document has no "seller" member type.
7. **"Fair trade" in Persian:** «تجارت عادلانه» is used throughout, as the booklet explains.
8. **Region of members:** Papital and Mehrbaf are in Tehran, Teeda in Golestan (Turkmen Sahra), Lena in Kerman,
   Parvandboom in Fars, Ormuz in Hormozgan (Minab), as the sources say. Haftdast House and Chagerd have no region.
9. **No invented content:** no news, events, prices, phone numbers or people were made up. Logos and photos of the
   members are not in the package; the secretariat adds them in the admin panel (اعضا › each member).

## Brand guide check

The site already uses the guide: gold `#cf9d2b` as the main colour with navy and white, and cyan `#14e6e0`, blue
`#031bff` and grey `#929e98` as accents. English text uses Arial; Persian uses IRANSans when the visitor's computer
has it, otherwise the free Vazirmatn font. IRANSans is a paid font and can only be served from the site once the House
buys a web licence. Two small inconsistencies in the guide itself:
- The dark colour is labelled `062817` (r6 g40 b23, a dark green), but its swatch is navy. The site uses navy `#1c1f4a`.
- The brown `#873319` reads as orange on screens, so it is kept for print.

## To check or complete

- Chagerd (point 2 above).
- The Iranian years in point 4.
- Logos, cover photos, phone numbers and the Instagram page of Lena Art Group for the member pages.
- Whether the two individual founders should be named on the About page (the sources do not name them).
- The English texts were written for a general international reader; a native-speaker read-through by the PR
  working group is still recommended before wide promotion.
