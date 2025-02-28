from deeprank.models.amino_acid import AminoAcid


alanine = AminoAcid("Alanine", "ALA", "A")
arginine = AminoAcid("Arginine", "ARG", "R")
asparagine = AminoAcid("Asparagine", "ASN", "N")
aspartate = AminoAcid("Aspartate", "ASP", "D")
protonated_aspartate = AminoAcid("Protonated Aspartate", "ASH", "D")
cysteine = AminoAcid("Cysteine", "CYS", "C")
cysteine_metal = AminoAcid("Cysteine Metal Ligand", "CYM", "C")
cysteine_iron = AminoAcid("Cysteine Iron Ligand", "CFE", "C")
cysteine_zinc = AminoAcid("Cysteine Zinc Ligand", "CYF", "C")
cysteine_phosphate = AminoAcid("Cysteine Phosphate", "CSP", "C")
glutamate = AminoAcid("Glutamate", "GLU", "E")
protonated_glutamate = AminoAcid("Protonated Glutamate", "GLH", "E")
glutamine = AminoAcid("Glutamine", "GLN", "Q")
glycine = AminoAcid("Glycine", "GLY", "G")
histidine = AminoAcid("Histidine", "HIS", "H")
histidine_phophate = AminoAcid("Histidine Phosphate", "NEP", "H")
isoleucine = AminoAcid("Isoleucine", "ILE", "I")
leucine = AminoAcid("Leucine", "LEU", "L")
lysine = AminoAcid("Lysine", "LYS", "K")
methionine = AminoAcid("Methionine", "MET", "M")
phenylalanine = AminoAcid("Phenylalanine", "PHE", "F")
proline = AminoAcid("Proline", "PRO", "P")
serine = AminoAcid("Serine", "SER", "S")
threonine = AminoAcid("Threonine", "THR", "T")
tryptophan = AminoAcid("Tryptophan", "TRP", "W")
tyrosine = AminoAcid("Tyrosine", "TYR", "Y")
valine = AminoAcid("Valine", "VAL", "V")
selenocysteine = AminoAcid("Selenocysteine", "SEC", "U")
pyrrolysine = AminoAcid("Pyrrolysine", "PYL", "O")
alysine = AminoAcid("Alysine", "ALY", "K")
methyllysine = AminoAcid("Methyllysine", "MLZ", "K")
dimethyllysine = AminoAcid("Dimethyllysine", "MLY", "K")
trimethyllysine = AminoAcid("Trimethyllysine", "3ML", "K")
epsilon_mthionine = AminoAcid("Epsilon Methionine", "MSE", "M")
hydroxy_proline = AminoAcid("Hydroxy Proline", "HYP", "P")
serine_phosphate = AminoAcid("Serine Phosphate", "SEP", "S")
threonine_phosphate = AminoAcid("Threonine Phosphate", "TOP", "T")
tyrosine_phosphate = AminoAcid("Tyrosine Phosphate", "TYP", "Y")
tyrosine_sulphate = AminoAcid("Tyrosine Sulphate", "TYS", "Y")
tyrosine_phosphate = AminoAcid("Tyrosine Phosphate", "PTR", "Y")
cyclohexane_alanine = AminoAcid("Cyclohexane Alanine", "CHX", "?")
unknown_amino_acid = AminoAcid("Unknown", "XXX", "X")


amino_acids = [alanine, arginine, asparagine, aspartate, cysteine, glutamate, glutamine, glycine,
               histidine, isoleucine, leucine, lysine, methionine, phenylalanine, proline, serine,
               threonine, tryptophan, tyrosine, valine]

amino_acids_by_code = {
    amino_acid.code: amino_acid
    for amino_acid in amino_acids
}
