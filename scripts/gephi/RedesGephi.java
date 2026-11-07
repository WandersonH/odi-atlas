// 07/11/2026 (C19.357): Gephi Toolkit sem interface — os mesmos algoritmos do Gephi (Modularity, ForceAtlas 2, OpenOrd),
// para cada GEXF pedido: estatísticas do Gephi, % de nós por comunidade, posições dos dois layouts, PNG e PDF de cada um.
// Pedido do responsável (07/11/2026, 19h25): "Force Atlas 2 pra ver comunidades e OpenOrd pra ver polarização; grupos
// pelo modularity e a % desses; registre o csv com os cálculos e print rede Gephi". O controle do Gephi do responsável
// pela tela não respondia (a janela Java não confirma o documento), então a rotina roda o Gephi Toolkit no runner.
// Uso: java -cp gephi-toolkit-all.jar:. RedesGephi <saida> <arquivo.gexf>...
import java.awt.Color;
import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.*;

import org.gephi.appearance.api.AppearanceController;
import org.gephi.appearance.api.AppearanceModel;
import org.gephi.appearance.api.Function;
import org.gephi.appearance.api.Partition;
import org.gephi.appearance.api.PartitionFunction;
import org.gephi.appearance.plugin.PartitionElementColorTransformer;
import org.gephi.appearance.plugin.RankingNodeSizeTransformer;
import org.gephi.appearance.plugin.palette.Palette;
import org.gephi.appearance.plugin.palette.PaletteManager;
import org.gephi.graph.api.*;
import org.gephi.io.exporter.api.ExportController;
import org.gephi.io.exporter.preview.PNGExporter;
import org.gephi.io.importer.api.Container;
import org.gephi.io.importer.api.ImportController;
import org.gephi.io.processor.plugin.DefaultProcessor;
import org.gephi.layout.plugin.forceAtlas2.ForceAtlas2;
import org.gephi.layout.plugin.forceAtlas2.ForceAtlas2Builder;
import org.gephi.layout.plugin.openord.OpenOrdLayout;
import org.gephi.layout.plugin.openord.OpenOrdLayoutBuilder;
import org.gephi.preview.api.PreviewController;
import org.gephi.preview.api.PreviewModel;
import org.gephi.preview.api.PreviewProperty;
import org.gephi.preview.types.EdgeColor;
import org.gephi.project.api.ProjectController;
import org.gephi.project.api.Workspace;
import org.gephi.statistics.plugin.ClusteringCoefficient;
import org.gephi.statistics.plugin.ConnectedComponents;
import org.gephi.statistics.plugin.Degree;
import org.gephi.statistics.plugin.GraphDensity;
import org.gephi.statistics.plugin.Modularity;
import org.gephi.statistics.plugin.EigenvectorCentrality;
import org.gephi.statistics.plugin.GraphDistance;
import org.gephi.statistics.plugin.Hits;
import org.gephi.statistics.plugin.PageRank;
import org.gephi.statistics.plugin.WeightedDegree;
import org.openide.util.Lookup;

public class RedesGephi {
    static String q(Object o) {
        String s = String.valueOf(o == null ? "" : o);
        return "\"" + s.replace("\"", "\"\"") + "\"";
    }

    public static void main(String[] args) throws Exception {
        File saida = new File(args[0]);
        saida.mkdirs();
        PrintWriter resumo = new PrintWriter(new File(saida, "gephi_resumo.csv"), StandardCharsets.UTF_8);
        resumo.println("caso,rede,dirigida,nos,arestas,densidade,grau_medio,grau_ponderado_medio,componentes,clustering_medio,diametro,caminho_medio,modularidade_q,comunidades,nos_componente_gigante,pct_componente_gigante,gc_densidade,gc_modularidade_q,gc_comunidades,gc_pct_comunidades,inferencia_estatistica_classes,top5_pagerank,top5_hits_autoridade,top5_autovetor,top5_intermediacao,separacao_openord_2_maiores,separacao_fa2_2_maiores,iteracoes_fa2,iteracoes_openord");
        for (int a = 1; a < args.length; a++) {
            File f = new File(args[a]);
            String caso = f.getParentFile().getName(), rede = f.getName().replace(".gexf", "");
            String nome = caso + "_" + rede;
            try {
                processa(f, saida, nome, caso, rede, resumo);
            } catch (Throwable t) {
                System.out.println("⛔ " + f + ": " + t);
                t.printStackTrace();
            }
            resumo.flush();
        }
        resumo.close();
    }

    static void processa(File f, File saida, String nome, String caso, String rede, PrintWriter resumo) throws Exception {
        ProjectController pc = Lookup.getDefault().lookup(ProjectController.class);
        pc.newProject();
        Workspace ws = pc.getCurrentWorkspace();
        ImportController ic = Lookup.getDefault().lookup(ImportController.class);
        Container c = ic.importFile(f);
        // 07/11/2026: mantém a direção do arquivo (respostas e contas → hashtags são dirigidas); o Modularity usa a vista não dirigida
        ic.process(c, new DefaultProcessor(), ws);
        GraphModel gm = Lookup.getDefault().lookup(GraphController.class).getGraphModel(ws);
        UndirectedGraph g = gm.getUndirectedGraph();  // reatribuído ao componente gigante adiante
        int n = g.getNodeCount(), m = g.getEdgeCount();

        GraphDensity dens = new GraphDensity();
        dens.setDirected(false);
        dens.execute(gm);
        Degree deg = new Degree();
        deg.execute(gm);
        ConnectedComponents cc = new ConnectedComponents();
        cc.setDirected(false);
        cc.execute(gm);
        ClusteringCoefficient cl = new ClusteringCoefficient();
        cl.setDirected(false);
        cl.execute(gm);
        Modularity mod = new Modularity();
        mod.setUseWeight(true);
        mod.setRandom(true);
        mod.setResolution(1.0);
        mod.execute(gm);
        Column colMod = gm.getNodeTable().getColumn(Modularity.MODULARITY_CLASS);

        // 07/11/2026 ("você não olhou o tamanho, não olhou densidade, eu veria tudo"): todo o painel Statistics do Gephi
        boolean dir = gm.isDirected();
        WeightedDegree wdeg = new WeightedDegree();
        wdeg.execute(gm);
        PageRank pr = new PageRank();
        pr.setDirected(dir);
        pr.setUseEdgeWeight(true);
        pr.execute(gm);
        Hits hits = new Hits();
        hits.setUndirected(!dir);
        hits.execute(gm);
        EigenvectorCentrality eig = new EigenvectorCentrality();
        eig.setDirected(dir);
        eig.execute(gm);
        String diam = "", camin = "";
        Column colBet = null;
        if (n <= 5000) {  // Network Diameter e Avg. Path Length (também gera intermediação/proximidade): caro acima disso
            GraphDistance gd = new GraphDistance();
            gd.setDirected(false);
            gd.setNormalized(true);
            gd.execute(gm);
            diam = String.format(Locale.ROOT, "%.0f", gd.getDiameter());
            camin = String.format(Locale.ROOT, "%.3f", gd.getPathLength());
            colBet = gm.getNodeTable().getColumn(GraphDistance.BETWEENNESS);
        }
        String infer = "";
        try {  // Statistical Inference (SBM), quando a versão do Toolkit traz a classe
            Object si = Class.forName("org.gephi.statistics.plugin.StatisticalInferenceClustering").getDeclaredConstructor().newInstance();
            si.getClass().getMethod("execute", GraphModel.class).invoke(si, gm);
            for (Column cl2 : gm.getNodeTable()) {
                if (cl2.getId().toLowerCase().contains("stat_inf") || cl2.getId().toLowerCase().contains("inference")) {
                    Set<Object> cls = new HashSet<>();
                    for (Node v : g.getNodes()) cls.add(v.getAttribute(cl2));
                    infer = "" + cls.size();
                }
            }
        } catch (Throwable t) {
            infer = "indisponível";
        }
        String topPr = top(g, gm.getNodeTable().getColumn(PageRank.PAGERANK)), topAut = top(g, gm.getNodeTable().getColumn(Hits.AUTHORITY)),
               topEig = top(g, gm.getNodeTable().getColumn(EigenvectorCentrality.EIGENVECTOR)), topBet = colBet == null ? "" : top(g, colBet);

        // 07/11/2026: Q e nº de comunidades da rede inteira; o desenho e os % ficam no componente gigante (como o filtro
        // Topology → Giant Component do Gephi). Em redes fragmentadas os pares soltos inflam o Q e viram centenas de "comunidades".
        double qTotal = mod.getModularity();
        Set<Object> clsTotal = new HashSet<>();
        for (Node v : g.getNodes()) clsTotal.add(v.getAttribute(colMod));
        int nTotal = n;
        Column colComp = gm.getNodeTable().getColumn(ConnectedComponents.WEAKLY);
        int gid = cc.getGiantComponent();
        List<Node> fora = new ArrayList<>();
        for (Node v : g.getNodes()) if (((Number) v.getAttribute(colComp)).intValue() != gid) fora.add(v);
        gm.getGraph().removeAllNodes(fora);  // só na cópia em memória do Toolkit; o GEXF não muda
        g = gm.getUndirectedGraph();
        n = g.getNodeCount();
        GraphDensity densGc = new GraphDensity();
        densGc.setDirected(false);
        densGc.execute(gm);
        Modularity modGc = new Modularity();
        modGc.setUseWeight(true);
        modGc.setRandom(true);
        modGc.setResolution(1.0);
        modGc.execute(gm);
        colMod = gm.getNodeTable().getColumn(Modularity.MODULARITY_CLASS);

        // % por comunidade no componente gigante (ordem decrescente de tamanho)
        Map<Integer, Integer> tam = new HashMap<>();
        for (Node v : g.getNodes()) tam.merge((Integer) v.getAttribute(colMod), 1, Integer::sum);
        List<Map.Entry<Integer, Integer>> ord = new ArrayList<>(tam.entrySet());
        ord.sort((x, y) -> y.getValue() - x.getValue());
        StringBuilder pcts = new StringBuilder();
        for (Map.Entry<Integer, Integer> e : ord) {
            if (pcts.length() > 0) pcts.append(" | ");
            pcts.append("classe ").append(e.getKey()).append(": ").append(String.format(Locale.ROOT, "%.2f", 100.0 * e.getValue() / n)).append("%");
        }

        // cores por comunidade (como Appearance → Partition → Modularity Class → Apply)
        AppearanceController ac = Lookup.getDefault().lookup(AppearanceController.class);
        AppearanceModel am = ac.getModel(ws);
        Function func = am.getNodeFunction(colMod, PartitionElementColorTransformer.class);
        Partition part = ((PartitionFunction) func).getPartition();
        Palette pal = PaletteManager.getInstance().generatePalette(part.size(g));
        part.setColors(g, pal.getColors());
        ac.transform(func);
        Column colTam = gm.getNodeTable().getColumn(dir ? Degree.INDEGREE : Degree.DEGREE);
        Function fTam = am.getNodeFunction(colTam, RankingNodeSizeTransformer.class);
        RankingNodeSizeTransformer tTam = (RankingNodeSizeTransformer) fTam.getTransformer();
        tTam.setMinSize(4f);
        tTam.setMaxSize(n > 5000 ? 60f : 80f);
        ac.transform(fTam);

        // ForceAtlas 2 (comunidades): LinLog, gravidade forte, scaling conforme o tamanho; depois evita sobreposição
        ForceAtlas2 fa2 = new ForceAtlas2Builder().buildLayout();
        fa2.setGraphModel(gm);
        fa2.resetPropertiesValues();
        fa2.setLinLogMode(true);
        fa2.setStrongGravityMode(true);
        fa2.setGravity(1.0);
        fa2.setScalingRatio(n > 2000 ? 20.0 : 10.0);
        fa2.setBarnesHutOptimize(n > 1000);
        fa2.setThreadsCount(Math.max(1, Runtime.getRuntime().availableProcessors()));
        int itFa2 = n > 20000 ? 600 : 1500;
        fa2.initAlgo();
        for (int i = 0; i < itFa2 && fa2.canAlgo(); i++) fa2.goAlgo();
        fa2.setAdjustSizes(true);
        for (int i = 0; i < 100 && fa2.canAlgo(); i++) fa2.goAlgo();
        fa2.endAlgo();
        Map<Node, float[]> posFa2 = new HashMap<>();
        for (Node v : g.getNodes()) posFa2.put(v, new float[]{v.x(), v.y()});
        exportaSeguro(ws, new File(saida, nome + "_forceatlas2.png"));
        double sepFa2 = separacao(g, colMod, ord);

        // OpenOrd (polarização): parâmetros padrão do Gephi
        OpenOrdLayout oo = (OpenOrdLayout) new OpenOrdLayoutBuilder().buildLayout();
        oo.setGraphModel(gm);
        oo.resetPropertiesValues();
        oo.initAlgo();
        int itOo = 0;
        while (oo.canAlgo() && itOo < 100000) { oo.goAlgo(); itOo++; }
        oo.endAlgo();
        exportaSeguro(ws, new File(saida, nome + "_openord.png"));
        double sepOo = separacao(g, colMod, ord);

        // nós: id, rótulo, classe, grau, posições dos dois layouts (o rótulo é o do GEXF público: pessoas comuns já em código)
        Column colDeg = gm.getNodeTable().getColumn(Degree.DEGREE);
        try (PrintWriter w = new PrintWriter(new File(saida, nome + "_nos_gephi.csv"), StandardCharsets.UTF_8)) {
            w.println("id,rotulo,modularity_class,grau,x_forceatlas2,y_forceatlas2,x_openord,y_openord");
            for (Node v : g.getNodes()) {
                float[] p = posFa2.get(v);
                w.println(q(v.getId()) + "," + q(v.getLabel()) + "," + v.getAttribute(colMod) + "," + v.getAttribute(colDeg) + ","
                        + p[0] + "," + p[1] + "," + v.x() + "," + v.y());
            }
        }
        resumo.println(String.join(",", q(caso), q(rede), "" + dir, "" + nTotal, "" + m,
                String.format(Locale.ROOT, "%.6f", dens.getDensity()), String.format(Locale.ROOT, "%.3f", deg.getAverageDegree()),
                String.format(Locale.ROOT, "%.3f", wdeg.getAverageDegree()),
                "" + cc.getConnectedComponentsCount(), String.format(Locale.ROOT, "%.4f", cl.getAverageClusteringCoefficient()), diam, camin,
                String.format(Locale.ROOT, "%.4f", qTotal), "" + clsTotal.size(), "" + n, String.format(Locale.ROOT, "%.2f", 100.0 * n / nTotal),
                String.format(Locale.ROOT, "%.6f", densGc.getDensity()), String.format(Locale.ROOT, "%.4f", modGc.getModularity()), "" + tam.size(), q(pcts), q(infer), q(topPr), q(topAut), q(topEig), q(topBet),
                String.format(Locale.ROOT, "%.3f", sepOo), String.format(Locale.ROOT, "%.3f", sepFa2), "" + itFa2, "" + itOo));
        System.out.println(nome + ": " + nTotal + " nós (gigante " + n + "), Q=" + String.format(Locale.ROOT, "%.4f", qTotal) + ", Q gigante=" + String.format(Locale.ROOT, "%.4f", modGc.getModularity()) + ", " + tam.size()
                + " comunidades, separação OpenOrd " + String.format(Locale.ROOT, "%.2f", sepOo));
    }

    // os 5 nós de maior valor numa coluna (rótulo do GEXF público: pessoas comuns já em código)
    static String top(UndirectedGraph g, Column col) {
        if (col == null) return "";
        List<Node> ns = new ArrayList<>();
        for (Node v : g.getNodes()) ns.add(v);
        ns.sort((x, y) -> Double.compare(((Number) y.getAttribute(col)).doubleValue(), ((Number) x.getAttribute(col)).doubleValue()));
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < Math.min(5, ns.size()); i++) {
            if (i > 0) b.append(" | ");
            b.append(ns.get(i).getLabel()).append(String.format(Locale.ROOT, " (%.4f)", ((Number) ns.get(i).getAttribute(col)).doubleValue()));
        }
        return b.toString();
    }

    // distância entre os centróides das duas maiores comunidades ÷ média dos raios (desvio das distâncias ao centróide)
    // > 2: blocos bem separados no desenho; ~1 ou menos: sobrepostos. Medida do desenho, exploratória.
    static double separacao(UndirectedGraph g, Column col, List<Map.Entry<Integer, Integer>> ord) {
        if (ord.size() < 2) return Double.NaN;
        int c1 = ord.get(0).getKey(), c2 = ord.get(1).getKey();
        double[] s = new double[6];
        List<float[]> p1 = new ArrayList<>(), p2 = new ArrayList<>();
        for (Node v : g.getNodes()) {
            int k = (Integer) v.getAttribute(col);
            if (k == c1) p1.add(new float[]{v.x(), v.y()});
            else if (k == c2) p2.add(new float[]{v.x(), v.y()});
        }
        double[] a = cent(p1), b = cent(p2);
        double d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        double r = (raio(p1, a) + raio(p2, b)) / 2;
        return r > 0 ? d / r : Double.NaN;
    }

    static double[] cent(List<float[]> ps) {
        double x = 0, y = 0;
        for (float[] p : ps) { x += p[0]; y += p[1]; }
        return new double[]{x / ps.size(), y / ps.size()};
    }

    static double raio(List<float[]> ps, double[] c) {
        double s = 0;
        for (float[] p : ps) s += Math.hypot(p[0] - c[0], p[1] - c[1]);
        return s / ps.size();
    }

    // uma falha na imagem não derruba os números da rede
    static void exportaSeguro(Workspace ws, File png) {
        try {
            exporta(ws, png);
        } catch (Throwable t) {
            System.out.println("⛔ imagem " + png.getName() + ": " + t);
        }
    }

    static void exporta(Workspace ws, File png) throws Exception {
        PreviewController prc = Lookup.getDefault().lookup(PreviewController.class);
        PreviewModel pm = prc.getModel(ws);
        pm.getProperties().putValue(PreviewProperty.SHOW_NODE_LABELS, Boolean.FALSE);
        pm.getProperties().putValue(PreviewProperty.EDGE_CURVED, Boolean.FALSE);
        pm.getProperties().putValue(PreviewProperty.EDGE_OPACITY, 25f);
        // 07/11/2026: espessura reescalada (na circulação o peso é em visualizações e as arestas cobriam o desenho)
        pm.getProperties().putValue(PreviewProperty.EDGE_RESCALE_WEIGHT, Boolean.TRUE);
        pm.getProperties().putValue(PreviewProperty.EDGE_RESCALE_WEIGHT_MIN, 0.1f);
        pm.getProperties().putValue(PreviewProperty.EDGE_RESCALE_WEIGHT_MAX, 1.5f);
        pm.getProperties().putValue(PreviewProperty.EDGE_COLOR, new EdgeColor(EdgeColor.Mode.SOURCE));
        pm.getProperties().putValue(PreviewProperty.NODE_BORDER_WIDTH, 0f);
        pm.getProperties().putValue(PreviewProperty.BACKGROUND_COLOR, Color.WHITE);
        prc.refreshPreview(ws);
        ExportController ec = Lookup.getDefault().lookup(ExportController.class);
        PNGExporter pe = (PNGExporter) ec.getExporter("png");
        pe.setWidth(2000);
        pe.setHeight(2000);
        pe.setWorkspace(ws);
        ec.exportFile(png, pe);
    }
}
