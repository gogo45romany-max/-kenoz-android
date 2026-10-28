import org.jf.baksmali.Baksmali;
import org.jf.baksmali.BaksmaliOptions;
import org.jf.dexlib2.DexFileFactory;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.iface.DexFile;
import org.jf.dexlib2.iface.MultiDexContainer;

import java.io.File;

public class BaksmaliDriver {
    public static void main(String[] args) throws Exception {
        MultiDexContainer<? extends DexFile> container =
                DexFileFactory.loadDexContainer(new File(args[0]), Opcodes.forApi(24));
        DexFile dex = container.getEntry(container.getDexEntryNames().get(0)).getDexFile();
        BaksmaliOptions options = new BaksmaliOptions();
        options.apiLevel = 24;
        boolean ok = Baksmali.disassembleDexFile(dex, new File(args[1]), 4, options);
        System.err.println("disassembled: " + ok);
    }
}
