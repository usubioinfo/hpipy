import shutil
import subprocess
import pandas as pd
import os
from pathlib import Path
from rpy2.robjects import r, pandas2ri
from rpy2.robjects.packages import importr
from multiprocessing import Pool, cpu_count
import gc

pandas2ri.activate()
gosim = importr('GOSemSim')


class GOSimilarity:
    """
    Class for calculating GO similarity scores and predicting interactions.
    """
        
    def __init__(self, log = None):
        """
        Initialize GOSimilarity class.

        :param log: Logger object for logging messages.
        :type log: str
        """

        self.log = log

        return

    
    # Interproscan path check
    def is_interproscan_installed(self):
        """
        Check if InterProScan is installed by verifying if 'interproscan.sh' is in the system's PATH.

        :return: Path to InterProScan if installed, or None otherwise.
        :rtype: str or None
        """

        interproscan_path = shutil.which("interproscan.sh")
        if interproscan_path:
            print(f"HPIpy: InterProScan installation found at '{interproscan_path}'")
            self.log.info(f"InterProScan installation found at '{interproscan_path}'")
            return interproscan_path
        else:
            return None
        
    
    # Run interproscan
    def run_interproscan(self, inputFasta, outputdir, data_directory):
        """
        Run InterProScan on the input FASTA file and save the output in the specified directory.

        :param inputFasta: The path to the input FASTA file.
        :param outputdir: Directory to store the output files generated by InterProScan.
        :param data_directory: Directory to save the downloaded files.

        :type inputFasta: str
        :type outputdir: str
        :type data_directory: str

        :return: None
        :rtype: None
        """

        inputClusters = f"{outputdir}/Clustering"
        interpro_output = f"{data_directory}/Interproscan_output"

        if not os.path.exists(interpro_output):
            os.makedirs(interpro_output)
            self.log.info("Interproscan output directory created successfully")
            print("HPIpy: Interproscan output directory created successfully")

        interproscan_path = self.is_interproscan_installed()

        if interproscan_path:
            try:
                self.log.info(f"Running Interproscan for '{inputFasta.split('.')[0]}' protein sequences")
                print(f"HPIpy: Running Interproscan for '{inputFasta.split('.')[0]}' protein sequences")

                interpro_outfile = f"{interpro_output}/{inputFasta.split('.')[0]}_interpro.tsv"
                interproscan_command = f"{interproscan_path} -i {inputClusters}/{inputFasta} -f tsv -o {interpro_outfile} -iprlookup -goterms"
                subprocess.run(interproscan_command, shell=True, check=True)

                print(f"HPIpy: InterProScan analysis for '{inputFasta.split('.')[0]}' sequences completed successfully.")
                self.log.info(f"InterProScan analysis for '{inputFasta.split('.')[0]}' sequences completed successfully.")

                return interpro_outfile
            
            except subprocess.CalledProcessError as e:
                print(f"HPIpy: Error running InterProScan: {e}")
                self.log.error(f"Error running InterProScan: {e}")
        
        else:
            print("HPIpy: InterProScan not found. Skipping this step.")
            self.log.info("InterProScan not found. Skipping this step.")
            pass

   
    # GO terms from interproscan results
    def extractGOTerms(self, input_file):
        """
        Process interproscan output file to separate multiple GO terms into individual rows for each protein. The processed data is saved as a CSV file.

        :param input_file: Path to the input TSV file containing the InterProScan results.
    
        :type input_file: str

        :return: None
        :rtype: None
        """

        df = pd.read_csv(input_file, delimiter='\t')
        df_filtered = df.iloc[:, [0, 13]]
        df_filtered.columns = ['gene', 'term']
        df_filtered = df_filtered[df_filtered['term'].notna()]
        df_filtered = df_filtered[df_filtered['term'] != '-']

        separated_data = []
        for _, row in df_filtered.iterrows():
            gene = row['gene']
            go_terms = row['term'].split('|')
            for go_term in go_terms:
                separated_data.append({'gene': gene, 'term': go_term})

        separated_df = pd.DataFrame(separated_data)
        outfile = f"{input_file.split('_interpro.tsv')[0]}_go.csv"
        separated_df.to_csv({outfile}, sep=',', index=False)

        return


    # GO terms from text files
    def readGOFile(self, filepath):
        """
        Reads a file (CSV or TSV) and checks if it has headers based on the presence of 'GO:' in the first row.
        If headers are missing, assigns default headers - 'ID' and 'GOterm'.
        
        :param filepath: Path to the input file (CSV or TSV).

        :type filepath: str

        :return: A pandas DataFrame with appropriate headers.
        :rtype: pandas.DataFrame
        """

        try:
            df = pd.read_csv(filepath, sep=None, engine='python', header=None)
        except pd.errors.ParserError:
            print(f"Could not parse the file {filepath} as a CSV or TSV.")
            return None

        # 'GO:' in first row
        if df.iloc[0].astype(str).str.contains("GO:").any():
            df.columns = ["ProteinID", "GOTerm"]
        else:
            df.columns = df.iloc[0]
            df = df[1:]
            df.columns = ["ProteinID", "GOTerm"]

        df.reset_index(drop=True, inplace=True)
        
        return df
    

    # Initialize semData
    def initializeSemData(self, ontology='BP'):
        """
        Initializes Gene Ontology (GO) semantic data for a specified ontology.

        :param ontology: The GO ontology to be used. Default is 'BP'.

        :type ontology: str

        :return: The initialized GO semantic data.
        :rtype: object or None
        """

        try:
            semData = gosim.godata(ont=ontology)
            return semData
        except Exception as e:
            print(f"Error initializing GO semantic data: {e}")
            return None


    # Calculate GO similarity
    def calculate_go_similarity(self, host_go, pathogen_go, semData, go_sim_method, go_combine):
        """
        Calculates the GO similarity between host and pathogen GO terms using the provided semantic data.

        :param host_go: The GO terms for the host protein.
        :param pathogen_go: The GO terms for the pathogen protein.
        :param semData: GO semantic data used for calculating the similarity.
        :param go_sim_method: The method to measure GO similarity.
        :param go_combine: The method to combine GO similarities.

        :type host_go: str or list
        :type pathogen_go: str or list
        :type semData: object
        :type go_sim_method: str
        :type go_combine: str

        :return: The calculated GO similarity score as a float. If an error occurs, returns None.
        :rtype: float or None
        """
        
        try:
            sim_score = gosim.mgoSim(host_go, pathogen_go, semData, measure=go_sim_method, combine=go_combine)
            return float(sim_score[0])
        except Exception as e:
            print(f"Error calculating GO similarity: {e}")
            return None


    ## Predict PPIs
    def process_pair(self, args):
        """
        Processes a pair of host and pathogen proteins and calculates their GO similarity score.

        :param args: A tuple containing the following elements:
            - host_protein: The identifier of the host protein.
            - host_go: GO terms associated with the host protein.
            - pathogen_protein: The identifier of the pathogen protein.
            - pathogen_go: GO terms associated with the pathogen protein.
            - semData: GO semantic data used for calculating the similarity.
            - go_sim_method: The method to measure GO similarity.
            - go_combine: The method to combine GO similarities.
            - simScore: The threshold similarity score.

        :type args: tuple
            - host_protein: str
            - host_go: str
            - pathogen_protein: str
            - pathogen_go: str
            - semData: object
            - go_sim_method: str
            - go_combine: str
            - simScore: float

        :return: A list containing the host protein, pathogen protein, host GO terms, pathogen GO terms, 
                and the calculated similarity score.
        :rtype: list or None
        """

        host_protein, host_go, pathogen_protein, pathogen_go, semData, go_sim_method, go_combine, simScore = args
        similarity_score = self.calculate_go_similarity(host_go, pathogen_go, semData, go_sim_method, go_combine)
        
        if similarity_score is not None and similarity_score > simScore:
            return [host_protein, pathogen_protein, host_go, pathogen_go, similarity_score]
        return None


    # Process pairs in chunks
    def chunk_pairs(self, pairs, chunk_size=10000000):
        """
        Yields successive chunks of pairs from the input list.

        :param pairs: A list of pairs to be divided into chunks.
        :param chunk_size: The maximum size of each chunk (default is 10,000,000).

        :type pairs: list
        :type chunk_size: int

        :return: A generator that yields chunks of pairs from the input list.
        :rtype: generator
        """

        for i in range(0, len(pairs), chunk_size):
            yield pairs[i:i + chunk_size]


    # Predict PPIs using GO similarity
    def predictGOPPIs(self, hostGOdf, pathogenGOdf, semData, go_sim_method, go_combine, simScore, chunk_size=10000000):
        """
        Predicts PPIs between host and pathogen proteins based on GO similarity scores.

        :param hostGOdf: A DataFrame containing the host proteins and their associated GO terms.
        :param pathogenGOdf: A DataFrame containing the pathogen proteins and their associated GO terms.
        :param semData: GO semantic data used for calculating the similarity.
        :param go_sim_method: The method to measure GO similarity.
        :param go_combine: The method to combine individual GO similarities.
        :param simScore: The threshold similarity score.
        :param chunk_size: The maximum number of pairs to process in each chunk (default is 10,000,000).

        :type hostGOdf: pandas.DataFrame
        :type pathogenGOdf: pandas.DataFrame
        :type semData: object
        :type go_sim_method: str
        :type go_combine: str
        :type simScore: float
        :type chunk_size: int

        :return: A DataFrame containing the predicted interactions.
        :rtype: pandas.DataFrame
        """
        
        predicted_interactions = []

        # Create pairs
        pairs = [
            (host_protein, host_go, pathogen_protein, pathogen_go, semData, go_sim_method, go_combine, simScore)
            for host_protein, host_go in zip(hostGOdf['ProteinID'], hostGOdf['GOTerm'])
            for pathogen_protein, pathogen_go in zip(pathogenGOdf['ProteinID'], pathogenGOdf['GOTerm'])
        ]
        
        print(f"HPIpy: Identified {len(pairs)} pairs of GO terms to be processed")
        
        # Process pairs in chunks
        count=0
        for chunk in self.chunk_pairs(pairs, chunk_size):
            count+=1
            print(f" >> Processing chunk: {count}")
            with Pool(processes=cpu_count()-1) as pool:
                results = pool.map(self.process_pair, chunk)
                predicted_interactions.extend(filter(None, results))

            del results
            gc.collect()

        predicted_df = pd.DataFrame(predicted_interactions, columns=['Host', 'Pathogen', 'Host_GO', 'Pathogen_GO', 'Similarity_Score'])

        return predicted_df