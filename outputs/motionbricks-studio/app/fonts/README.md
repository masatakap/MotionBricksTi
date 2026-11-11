# UI fonts

Inter (regular weight 400; optical size 14 default), from:
https://github.com/google/fonts/tree/main/ofl/inter

Noto Sans JP Regular (static Japanese subset OTF), from:
https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/JP

Downloaded 2026-10-30. Both are distributed under the SIL Open Font License 1.1;
see the accompanying Inter-OFL.txt and NotoSansJP-OFL.txt. The fonts are not
modified. The application merges Noto Sans JP into Inter for missing glyphs at
runtime, with a 19 px base size (previously 15 px).

Simplified Chinese UI uses Noto Sans SC Regular from:
https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/SC

It uses the same NotoSansJP-OFL.txt license. For Chinese, SC glyphs take priority;
for Japanese, JP glyphs take priority. Both retain the other font as fallback.

Noto Sans JP embedded copyright notice:

© 2014-2021 Adobe (http://www.adobe.com/).

Noto Sans SC embedded copyright notice:

© 2014-2021 Adobe (http://www.adobe.com/).
