import brut.androlib.mod.SmaliMod;
import org.jf.dexlib2.Opcodes;
import org.jf.dexlib2.writer.builder.DexBuilder;
import org.jf.dexlib2.writer.io.FileDataStore;
import org.jf.dexlib2.writer.DexWriter;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class SmaliDriver {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: SmaliDriver <smaliDir> <out.dex> [api]");
            System.exit(2);
        }
        int api = args.length > 2 ? Integer.parseInt(args[2]) : 24;
        File root = new File(args[0]);
        List<File> files = new ArrayList<File>();
        collect(root, files);
        Collections.sort(files);
        DexBuilder db = new DexBuilder(Opcodes.forApi(api));
        int ok = 0, fail = 0;
        for (File f : files) {
            if (!f.getName().endsWith(".smali")) continue;
            boolean r = SmaliMod.assembleSmaliFile(f, db, api, true, false);
            if (r) ok++; else { fail++; System.err.println("FAILED: " + f); }
        }
        System.err.println("assembled ok=" + ok + " failed=" + fail);
        if (fail > 0) System.exit(1);
        FileDataStore store = new FileDataStore(new File(args[1]));
        db.writeTo(store);
        store.close();
        System.err.println("wrote " + args[1]);
    }

    private static void collect(File dir, List<File> out) {
        File[] kids = dir.listFiles();
        if (kids == null) return;
        for (File k : kids) {
            if (k.isDirectory()) collect(k, out);
            else out.add(k);
        }
    }
}
