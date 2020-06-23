# Port of Microsoft GW-BASIC to Z80

This repo contains an ongoing port of Microsoft's GW-BASIC interpreter from 8086 to Z80.  This
is being accomplished by writing a porting tool, named 'conv.py', which is able to convert the
source files in the Microsoft Macro Assembler format to Z80.  This tool isn't a general purpose
ISA conversion tool, but something tailor made for this particular code base.

## License

All original files within this repo released by Microsoft are released under
the [MIT (OSI) License]( https://en.wikipedia.org/wiki/MIT_License) as per
the [LICENSE file](https://github.com/Microsoft/GW-BASIC/blob/master/LICENSE) stored in
the root of this repo.

The conversion tool, [`conv`](conv), is released under GNU GPL version 2.

## Contributing

Pull requests to improve the converter are welcome!

## Status

A lot of the ASM files in this repo can be translated to Z80, but the generated code isn't
perfect yet; a lot of instructions being generated are invalid and the code generator has to
be reviewed.  Having said that, the generator is able to start and finish going through these
files:

  * ADVGRP.ASM
  * BIPRTU.ASM
  * BIPTRG.ASM
  * BISTRS.ASM
  * DSKCOM.ASM
  * FIVEO.ASM
  * GENGRP.ASM
  * GIOCAS.ASM
  * GIOCON.ASM
  * GIOTBL.ASM
  * GWEVAL.ASM
  * GWLIST.ASM
  * GWMAIN.ASM
  * MACLNG.ASM
  * OEM.H
  * IBMRES.ASM
