
import sys
import re
import math
from itertools import groupby 
# import parasail
import edlib

from collections import namedtuple, defaultdict

from modules import colinear_solver 
from modules import help_functions


mam = namedtuple('Mam', ['x', 'y', 'c', 'd', 'val', "min_segment_length", "exon_id", "ref_chr_id"])
globals()[mam.__name__] = mam # Global needed for multiprocessing


def cigar_to_seq(cigar, query, ref):
    cigar_tuples = []
    result = re.split(r'[=DXSMI]+', cigar)
    i = 0
    for length in result[:-1]:
        i += len(length)
        type_ = cigar[i]
        i += 1
        cigar_tuples.append((int(length), type_ ))

    r_index = 0
    q_index = 0
    q_aln = []
    r_aln = []
    for length_ , type_ in cigar_tuples:
        if type_ == "=" or type_ == "X":
            q_aln.append(query[q_index : q_index + length_])
            r_aln.append(ref[r_index : r_index + length_])

            r_index += length_
            q_index += length_
        
        elif  type_ == "I":
            # insertion w.r.t. reference
            r_aln.append('-' * length_)
            q_aln.append(query[q_index: q_index + length_])
            #  only query index change
            q_index += length_

        elif type_ == 'D':
            # deletion w.r.t. reference
            r_aln.append(ref[r_index: r_index + length_])
            q_aln.append('-' * length_)
            #  only ref index change
            r_index += length_
        
        else:
            print("error")
            print(cigar)
            sys.exit()

    return  "".join([s for s in q_aln]), "".join([s for s in r_aln]), cigar_tuples

def cigar_to_accuracy(cigar_string):
    cigar_tuples = []
    result = re.split(r'[=DXSMI]+', cigar_string)
    i = 0
    for length in result[:-1]:
        i += len(length)
        type_ = cigar_string[i]
        i += 1
        cigar_tuples.append((int(length), type_ ))
    # print(cigar_tuples)
    aln_length = 0
    matches = 0
    for length_ , type_ in cigar_tuples:
        if type_ == "=":
            matches += length_
            aln_length += length_
        else :
            aln_length += length_
    return matches / float(aln_length)



def edlib_alignment(query, target, mode = "HW", task = 'locations', k=-1):
    result = edlib.align(query, target, task=task, mode=mode, k=k)
    if result['editDistance'] == -1:
        return [0,0], -1, 0
    
    if task == 'locations':
        locations = result['locations']
        ref_start, ref_stop = locations[0][0], locations[0][1]
        accuracy = ((ref_stop - ref_start) - result['editDistance'])/ (ref_stop - ref_start)
    elif task == 'path':
        locations = result['locations']
        ref_start, ref_stop = locations[0][0], locations[0][1]
        cigar_string = result["cigar"]
        accuracy = cigar_to_accuracy(cigar_string)
        # print(accuracy, ( (ref_stop - ref_start) - result['editDistance'])/ (ref_stop - ref_start))
        # print(cigar_string, result['editDistance'], locations, accuracy)
        query_alignment, target_alignment, cigar_tuples = cigar_to_seq(cigar_string, query, target[ref_start: ref_stop+1 ])
        # print(cigar_string)
        # print(query_alignment)
        # print(target_alignment)

    return result['locations'], result['editDistance'], accuracy #, query_alignment, target_alignment



def calc_complessed_score(read_alignment, ref_alignment, m, n):
    """
        Raw score: R = aI +  bX - cO -  dG
        lambda=1.37 and K=0.711
        E=mn2**-S
    """
    states = ['I' if n1 == n2 else 'G' if n1 == '-' or n2 == '-' else 'X' for n1, n2 in zip(read_alignment,ref_alignment) ]
    compressed_profile = [ (element, len(list(i))) for element, i in groupby(states)] 
    print(compressed_profile)
    # return evalue


def calc_evalue(read_alignment, ref_alignment, m, n):
    """
        Raw score: R = aI +  bX - cO -  dG
        lambda=1.37 and K=0.711
        E=mn2**-S
    """
    a, b, c, d = 1, -1, 1,  1
    lambda_=1.37
    K=0.711

    states = ['I' if n1 == n2 else 'G' if n1 == '-' or n2 == '-' else 'X' for n1, n2 in zip(read_alignment,ref_alignment) ]
    I = states.count('I')
    X = states.count('X')
    G = states.count('G')
    O =  len([s1 for s1, s2 in zip(states[:-1],states[1:]) if s1 != s2 and s2 == 'G'])
    if states[0] == 'G': # starts with a gap
        O += 1
    raw_score = a*I +  b*X - c*O -  d*G
    if raw_score < 0:
        raw_score = 0
    bit_score = (lambda_*raw_score - math.log(K) )/ math.log(2)
    evalue = m*n*2**(-bit_score)
    # print(read_alignment)
    # print(ref_alignment)
    print(I,X,G,O)
    print(raw_score, bit_score, evalue)
    return evalue

def contains(sub, pri):
    M, N = len(pri), len(sub)
    i, LAST = 0, M-N+1
    while True:
        try:
            found = pri.index(sub[0], i, LAST) # find first elem in sub
        except ValueError:
            return False
        if pri[found:found+N] == sub:
            return True
        else:
            i = found+1

def is_overlapping(a_start,a_stop, b_start,b_stop):
    return (int(a_start) <= int(b_start) <= int(a_stop) )  or (int(a_start) <= int(b_stop) <= int(a_stop)) or (int(b_start) <= int(a_start) <= int(a_stop) <= int(b_stop) )


def get_unique_exon_and_flank_locations(solution, parts_to_segments, segment_id_to_choordinates):
    wiggle_overlap = 5
    unique_part_locations = []
    segment_hit_locations = []
    flank_hit_locations = []
    # start_part_offset, part_pos_max = 0, 2**32
    # prev_part = ""
    # approximate_hit_locations = { } # { part_id : (ref_start, ref_stop, read_start, read_stop) }
    partial_segment_hit_locations = { }
    partial_flank_hit_locations = { } 
    choord_to_exon_id = {}

    # these two variables are used to check which exos are considered start and stop exons in the read alignment
    # any such exons will be allowed to align with segments of hits (emulating semi-global alignments)
    first_part_stop = 2**32
    last_part_start = 0
    # print(solution)
    for mem in solution:
        ref_chr_id, ref_start, ref_stop =  mem.exon_part_id.split('^')
        ref_start, ref_stop = int(ref_start), int(ref_stop)
        # print("processing", mem)
        if len(unique_part_locations) == 0 or (ref_chr_id, ref_start, ref_stop) != unique_part_locations[-1]: # not to add repeated identical parts
            unique_part_locations.append((ref_chr_id, ref_start, ref_stop))
            # print("Added to unique_part_locations", (ref_chr_id, ref_start, ref_stop))
        exon_ids = parts_to_segments[ref_chr_id][(ref_start, ref_stop)]
        if not exon_ids: # is a flank
            # print("LOL what", ref_chr_id, ref_start, ref_stop)
            # sys.exit()
            # print("Is flank", (ref_chr_id, ref_start, ref_stop))
            flank_hit_locations.append((ref_chr_id, ref_start, ref_stop))  
            # if ref_start - wiggle_overlap <= mem.x < mem.y <= ref_stop + wiggle_overlap:
                # print("made wiggle", ref_start, mem.x , mem.y ,ref_stop)
            if (ref_chr_id, ref_start, ref_stop) in partial_flank_hit_locations:
                # print("in segm, updating")
                partial_flank_hit_locations[(ref_chr_id, ref_start, ref_stop)][1] =  mem.y
                partial_flank_hit_locations[(ref_chr_id, ref_start, ref_stop)][3] =  mem.d
            else: 
                # print("in segm")
                partial_flank_hit_locations[(ref_chr_id, ref_start, ref_stop)] = [mem.x, mem.y, mem.c, mem.d]       
        else:
            # print("Is not a flank, ie exon", (ref_chr_id, ref_start, ref_stop), exon_ids)

            # get all exons associated with the part and see if they are hit
            if ref_stop <= first_part_stop:
                first_part_stop = ref_stop
            if ref_start >= last_part_start:
                last_part_start = ref_start

            for exon_id in exon_ids:
                # exon overlaps with mem
                s_start, s_stop = segment_id_to_choordinates[exon_id]
                if is_overlapping(s_start,s_stop, mem.x, mem.y):
                    choord_to_exon_id[(ref_chr_id, s_start, s_stop)] = exon_id
                    # print(s_start, s_stop)
                    # print(s_start,s_stop,  mem.x, mem.y )
                    segment_hit_locations.append( (ref_chr_id, s_start, s_stop) )
                    # if s_start - wiggle_overlap <= mem.x < mem.y <= s_stop + wiggle_overlap:
                        # print("Adding", (ref_chr_id, s_start, s_stop) )
                    if (ref_chr_id, s_start, s_stop) in partial_segment_hit_locations:
                        partial_segment_hit_locations[(ref_chr_id, s_start,s_stop)][1] =  mem.y
                        partial_segment_hit_locations[(ref_chr_id, s_start,s_stop)][3] =  mem.d
                        # print("Upd", (mem.y, mem.d) )
                    else: 
                        partial_segment_hit_locations[(ref_chr_id, s_start,s_stop)] = [mem.x, mem.y, mem.c, mem.d]
                        # print("Init", (mem.x, mem.y, mem.c, mem.d) )


        # if (ref_chr_id, ref_start, ref_stop) in approximate_hit_locations:
        #     # increase the end coordinates on the same part reference
        #     approximate_hit_locations[(ref_chr_id, ref_start, ref_stop)][1] = mem.y 
        #     approximate_hit_locations[(ref_chr_id, ref_start, ref_stop)][3] = mem.d
        # else:
        #     approximate_hit_locations[(ref_chr_id, ref_start, ref_stop)] = [mem.x, mem.y, mem.c, mem.d]
    
    # remove duplicates added and sort to get unique ones
    segment_hit_locations = list(set(segment_hit_locations))
    segment_hit_locations.sort(key= lambda x: x[1])
    # print(segment_hit_locations)
    # print(partial_segment_hit_locations)
    # print(flank_hit_locations)
    # print(partial_flank_hit_locations)
    # print(approximate_hit_locations)
    # print("segment_hit_locations", segment_hit_locations)
    # print("unique_part_locations", unique_part_locations)
    return segment_hit_locations, partial_segment_hit_locations, flank_hit_locations, partial_flank_hit_locations, choord_to_exon_id, first_part_stop, last_part_start


def get_unique_segment_and_flank_choordinates(segment_hit_locations, partial_segment_hit_locations, flank_hit_locations, partial_flank_hit_locations, choord_to_exon_id, parts_to_segments, segment_id_to_choordinates, segment_to_gene, gene_to_small_segments):
    # compress unique exons to only do alignment once 
    unique_segment_choordinates = defaultdict(set)
    unique_segment_choordinates_partial_hits = defaultdict(set)
    unique_flank_choordinates = defaultdict(set)
    unique_flank_choordinates_partial_hits = defaultdict(set)

    # add all small segments here at once
    if segment_hit_locations:
        unique_genes = set(gene_id for (ref_chr_id, s_start, s_stop) in segment_hit_locations for gene_id in segment_to_gene[choord_to_exon_id[(ref_chr_id, s_start, s_stop)]])
        small_segments = set(small_segment_id for gene_id in unique_genes for small_segment_id in gene_to_small_segments[gene_id])
        ref_chr_id = segment_hit_locations[0][0]
        for small_segment_id in small_segments:
            small_s_start, small_s_stop = segment_id_to_choordinates[small_segment_id]
            if (ref_chr_id,small_s_start, small_s_stop) not in unique_segment_choordinates:
                # print("adding small exon,", small_s_stop - small_s_start)
                unique_segment_choordinates[ (ref_chr_id, small_s_start, small_s_stop) ].add(small_segment_id)

    for (ref_chr_id, s_start, s_stop) in segment_hit_locations:
        # exon_ids = parts_to_segments[ref_chr_id][(s_start, s_stop)]
        # print(parts_to_segments)
        exon_id = choord_to_exon_id[(ref_chr_id, s_start, s_stop)]
        unique_segment_choordinates[ (ref_chr_id, s_start, s_stop) ].add(exon_id)
        
        if (ref_chr_id, s_start, s_stop) in partial_segment_hit_locations:
            segm_ref_start, segm_ref_stop, segm_read_start, segm_read_stop = partial_segment_hit_locations[(ref_chr_id, s_start, s_stop)]
            unique_segment_choordinates_partial_hits[(ref_chr_id, s_start, s_stop) ] =  (ref_chr_id, segm_ref_start, segm_ref_stop, exon_id)

        # also add all small exons that may be smaller than minimum MEM size
        # unique_genes = set(gene_id for exon_id in exon_ids for gene_id in segment_to_gene[exon_id])
        
        # unique_genes = set(gene_id for gene_id in segment_to_gene[exon_id])
        # small_segments = set(small_segment_id for gene_id in unique_genes for small_segment_id in gene_to_small_segments[gene_id]) 
        # # print(small_segments)
        # for small_segment_id in small_segments:
        #     small_s_start, small_s_stop = segment_id_to_choordinates[small_segment_id]
        #     if (ref_chr_id,small_s_start, small_s_stop) not in unique_segment_choordinates_old:
        #         # print("adding small exon,", small_s_stop - small_s_start)
        #         unique_segment_choordinates_old[ (ref_chr_id, small_s_start, small_s_stop) ].add(small_segment_id)

    for (ref_chr_id, ref_start, ref_stop) in flank_hit_locations:
        # print((ref_start, ref_stop), exon_ids)
        # if not exon_ids: # is a flank
        unique_flank_choordinates[ (ref_chr_id, ref_start, ref_stop) ] = set()
        segm_ref_start, segm_ref_stop, segm_read_start, segm_read_stop = partial_flank_hit_locations[(ref_chr_id, ref_start, ref_stop)]
        # case read starts     read:     [ > 0.2*e_len]   ----------------------------...
        # within start exon    exon: --------------------------------
        if (segm_ref_start - ref_start) > 0.05*(ref_stop - ref_start):
            unique_flank_choordinates_partial_hits[(ref_chr_id, ref_start, ref_stop) ] =  (ref_chr_id, segm_ref_start, segm_ref_stop)

        # case read ends       read:  ...----------------------------   [ > 0.2*e_len]   
        # within end exon      exon:                      ---------------------------------
        if (ref_stop - segm_ref_stop ) > 0.05*(ref_stop - ref_start):
            unique_flank_choordinates_partial_hits[(ref_chr_id,  ref_start, ref_stop) ] =  (ref_chr_id, segm_ref_start, segm_ref_stop)
    # print(unique_segment_choordinates)
    # sys.exit()
    # assert unique_segment_choordinates_old == unique_segment_choordinates_new
    return unique_segment_choordinates, unique_segment_choordinates_partial_hits, unique_flank_choordinates, unique_flank_choordinates_partial_hits


def add_exon_to_mam(read_seq, ref_chr_id, exon_seq, e_start, e_stop, exon_id, mam_instance, min_acc, annot_label):
    if e_stop - e_start >= 5:
        # exon_seq = ref_segment_sequences[ref_chr_id][(e_start, e_stop)]
        # print((e_start, e_stop))
        # print(exon_seq == ref_seq2)
        # assert exon_seq == ref_seq2
        # print(exon_id, e_stop - e_start)
        # align them to the read and get the best approxinate match
        if e_stop - e_start >= 9:
            locations, edit_distance, accuracy = edlib_alignment(exon_seq, read_seq, mode="HW", task = 'path', k = 0.4*min(len(read_seq), len(exon_seq)) ) 
            # print(locations, edit_distance, accuracy)
            # if 'flank' in exon_id:
            # print(exon_seq)
            if edit_distance >= 0 and accuracy > min_acc:
                # calc_complessed_score(read_alignment, ref_alignment, len(read_seq), len(exon_seq))
                # e_score = calc_evalue(read_alignment, ref_alignment, len(read_seq), len(exon_seq))
                # start, stop = locations[0]
                # if len(locations) > 1:
                #     print("had more", e_stop - e_start, locations)

                # print(accuracy)
                # print((e_start, e_stop), locations, edit_distance, min_segment_length, accuracy, (min_segment_length - edit_distance)/float(min_segment_length), (stop - start + 1)*accuracy, (stop - start + 1 - edit_distance)* accuracy, (min_segment_length - edit_distance)/float(min_segment_length))
                # print(exon_seq)
                # only take unique start locations by taking the highest accuracy from each hit with the same position
                considered_starts = set()
                max_score = 0
                # locations_filtered = set(s for locs in zip(locations[:-1],locations[1:]) for s in locs if locs[0][0] != locs[1][0])
                # locations_filtered.add(locations[0])
                # locations_filtered.add(locations[-1])
                # print(locations)
                # print(locations_filtered)
                # print("LOOOOOOCS")
                for start, stop in locations:
                    min_segment_length = stop - start + 1 #Edlib end location is inclusive
                    acc_approx = max( (min_segment_length - edit_distance)/min_segment_length, accuracy)
                    score = acc_approx*min_segment_length
                    if start in considered_starts:
                        if score <= max_score:
                            continue
                    else:
                        max_score = score
                    # score = accuracy*matches #(min_segment_length - edit_distance) # accuracy*min_segment_length
                    mam_tuple = mam(e_start, e_stop, start, stop, 
                            score, min_segment_length,  exon_id + annot_label, ref_chr_id) 
                    mam_instance.append(mam_tuple)
                    considered_starts.add(start)
                    max_score = score

        
        else: # small exons between 5-9bp needs exact match otherwise too much noise
            locations, edit_distance, accuracy= edlib_alignment(exon_seq, read_seq, mode="HW", task = 'path', k = 0 )
            # print("HEEERE", exon_seq, locations, e_start, e_stop,ref_chr_id)
            if edit_distance == 0:
                # print("perfect matches:",exon_seq, locations)
                score = len(exon_seq)
                # calc_complessed_score(read_alignment, ref_alignment, len(read_seq), len(exon_seq))
                # e_score = calc_evalue(read_alignment, ref_alignment, len(read_seq), len(exon_seq))
                # for exon_id in all_exon_ids: break # only need one of the redundant exon_ids
                # exon_id = all_exon_ids.pop()
                considered_starts = set()
                for start, stop in locations:
                    if start in considered_starts:
                        continue
                    mam_tuple = mam(e_start, e_stop, start, stop, 
                            score, score,  exon_id + annot_label, ref_chr_id) 
                    mam_instance.append(mam_tuple)
                    considered_starts.add(start)
    else:
        pass
        # warning_log_file.write("not aligning exons smaller than 5bp: {0}, {1}, {2}, {3}.\n".format(ref_chr_id, e_start, e_stop, ref_segment_sequences[ref_chr_id][(e_start, e_stop)])) # TODO: align these and take all locations

    if  e_stop - e_start >= 0.8*len(read_seq): # read is potentially contained within exon 
        # print()
        # print("aligning read to exon")
        locations, edit_distance, accuracy = edlib_alignment(read_seq, exon_seq, mode="HW", task = 'path', k = 0.4*min(len(read_seq), len(exon_seq)) )
        # print(exon_seq)
        # print((e_start, e_stop), locations, len(exon_seq), len(read_seq), locations,  edit_distance, accuracy)
        # print()
        if edit_distance >= 0:
            # min_segment_length = min( len(exon_seq) ,len(read_seq) )
            # score = min_segment_length - edit_distance #/len(read_seq)
            
            start, stop = locations[0]
            min_segment_length = stop - start + 1 #Edlib end location is inclusive
            score = accuracy*min_segment_length #matches #*(min_segment_length - edit_distance) #accuracy*min_segment_length  #/len(read_seq)
            # print("LOOK:", min_segment_length, edit_distance, score, locations)
            # if e_score < 1.0:
            if accuracy > min_acc: #(min_segment_length -  edit_distance)/float(min_segment_length) > min_acc:
                start, stop = 0, len(read_seq) - 1
                # covered_regions.append((start,stop, score, exon_id, ref_chr_id))
                # for exon_id in all_exon_ids:
                #     mam_tuple = mam(e_start, e_stop, start, stop, 
                #             score, min_segment_length,  exon_id, ref_chr_id)
                #     mam_instance.append(mam_tuple)
                
                # for exon_id in all_exon_ids: break
                # exon_id = all_exon_ids.pop()
                mam_tuple = mam(e_start, e_stop, start, stop, 
                        score, min_segment_length,  exon_id + annot_label, ref_chr_id)
                mam_instance.append(mam_tuple)
    


def main(solution, ref_segment_sequences, ref_flank_sequences, parts_to_segments, segment_id_to_choordinates, segment_to_gene, gene_to_small_segments, read_seq, warning_log_file, min_acc):
    """
        NOTE: if paramerer task = 'path' is given to edlib_alignment function calls below, it will give exact accuracy of the aligmnent but the program will be ~40% slower to calling task = 'locations'
            Now we are approxmating accuracy by dividing by start and end of the reference coordinates of the alignment. This is not good approw if there is a large instertion
            in the exon w.r.t. the read.
    """
    # chained_parts_seq = []
    # chained_parts_ids = []
    # prev_ref_stop = -1
    # predicted_transcript = []
    # predicted_exons = []
    # covered_regions = []

    segment_hit_locations, partial_segment_hit_locations, flank_hit_locations, partial_flank_hit_locations, choord_to_exon_id, first_part_stop, last_part_start = get_unique_exon_and_flank_locations(solution, parts_to_segments, segment_id_to_choordinates)
    # print()
    # print(segment_hit_locations)
    # print()

    unique_segment_choordinates, unique_segment_choordinates_partial_hits, \
    unique_flank_choordinates, unique_flank_choordinates_partial_hits = get_unique_segment_and_flank_choordinates(segment_hit_locations, partial_segment_hit_locations, flank_hit_locations, partial_flank_hit_locations, \
                                                                                                     choord_to_exon_id, parts_to_segments, segment_id_to_choordinates, segment_to_gene, gene_to_small_segments)
    # print()
    # print('unique_exon_choordinate segments', unique_segment_choordinates_partial_hits)
    # for t in sorted(unique_segment_choordinates_partial_hits):
    #     print(t)
    # print()
    # sys.exit()

    # unique_exon_segments = get_segments_of_exons(approximate_hit_locations, unique_segment_choordinates)
    # all_potential_hits = unique_segment_choordinates + unique_exon_segments

    # In the chainer solvers, start and end cordinates are always inclusive, i.e. 1,10 means that the mem
    # spans and includes bases 1,2,...,10. In python indexing of strings we would slice out this interval
    # as [1:11], therefore we subtract 1 from the end of the interval before adding it to MAM instance
    mam_instance = []
    for (ref_chr_id, s_start, s_stop), all_exon_ids in sorted(unique_segment_choordinates.items(), key=lambda x: x[0][1]):
        segment_seq = ref_segment_sequences[ref_chr_id][(s_start, s_stop)]
        exon_id = all_exon_ids.pop()
        # print("Testing full segment", s_start, s_stop, exon_id, segment_seq)
        add_exon_to_mam(read_seq, ref_chr_id, segment_seq, s_start, s_stop, exon_id, mam_instance, min_acc, annot_label = '_full_segment' )


    # add the flanks if any in the solution But they are required to be start and end flanks of the part MEMs and not overlapping any exons (i.e., the exon hits to be considered)
    for (ref_chr_id, f_start, f_stop), _ in sorted(unique_flank_choordinates.items(), key=lambda x: x[0][1]):
        flank_seq = ref_flank_sequences[ref_chr_id][(f_start, f_stop)]
        flank_id = "flank_{0}_{1}".format(f_start, f_stop)
        # print("Testing full flank:", f_start, f_stop, flank_seq )
        # if (f_stop <= segment_hit_locations[0][1]) or (segment_hit_locations[-1][2] <= f_start): # is start flank
        add_exon_to_mam(read_seq, ref_chr_id, flank_seq, f_start, f_stop, flank_id, mam_instance, min_acc, annot_label = '_full_flank' )


    # Consider partial hits here after all full exons and flanks have been aligned. A segment is tested for 
    # all exons/flanks with start/ end coordinate after the choort of the last valid MAM added!

    # Do not allow partial hits of internal exons yet (ONLY START and END EXON FOR NOW) because these can generate spurious optimal alignments.
    # print(unique_segment_choordinates_partial_hits)
    # print(segment_hit_locations)
    # print("first segment_hit_locations:", first_part_stop, segment_hit_locations[0][2])
    # print("Last segment_hit_locations:", last_part_start, segment_hit_locations[-1][1])
    if len(mam_instance) > 0:
        first_valid_mam_stop = min([m.y for m in mam_instance])
        last_valid_mam_start = max([m.x for m in mam_instance])
    else:
        first_valid_mam_stop = -1
        last_valid_mam_start = 2**32
    final_first_stop = max(first_part_stop, first_valid_mam_stop)
    final_last_start = min(last_part_start, last_valid_mam_start)
    # print(first_part_stop >= first_valid_mam_stop, "OMG")
    # print(last_part_start <= last_valid_mam_start, "OMG2")
    segm_already_tried = set()
    for (ref_chr_id, e_start, e_stop) in unique_segment_choordinates_partial_hits:
        # ref_chr_id, e_start, e_stop, exon_id = unique_segment_choordinates_partial_hits[(ref_chr_id, s_start, s_stop)]
        ref_chr_id, s_start, s_stop, exon_id = unique_segment_choordinates_partial_hits[(ref_chr_id, e_start, e_stop)]
        # is first or last hit exon only
        # print(e_stop, first_valid_mam_stop, first_part_stop, segment_hit_locations[0][2])
        # print(e_start, last_valid_mam_start, last_part_start, segment_hit_locations[-1][1])
        exon_seq = ref_segment_sequences[ref_chr_id][(e_start, e_stop)]        
        if e_stop <= final_first_stop: # is start exon
            segment_seq = exon_seq[s_start - e_start:  ]  # We allow only semi global hit towards one end (the upstream end of the read)
            # print()
            if segment_seq not in segm_already_tried and len(segment_seq) > 5:
                # print("testing partial_hit beginning:", exon_id, e_start, e_stop, s_start, s_stop, final_first_stop, segment_seq)
                add_exon_to_mam(read_seq, ref_chr_id, segment_seq, e_start, e_stop, exon_id, mam_instance, min_acc, annot_label = '_partial_segment_start')
                segm_already_tried.add(segment_seq)
        elif final_last_start <= e_start: # is end_exon
            # print(len(exon_seq), s_start,s_stop, e_start, e_stop, len(exon_seq), s_start - e_start, len(exon_seq) - (e_stop - s_stop +1))
            # segment_seq = exon_seq[s_start - e_start: len(exon_seq) - (e_stop - (s_stop + 1)) ]  # segment is MEM coordinated i.e. inclusive, so we subtract one here
            segment_seq = exon_seq[: len(exon_seq) - (e_stop - (s_stop + 1)) ]  # segment is MEM coordinated i.e. inclusive, so we subtract one here, allow semi global hit towards one end (the downstream end of the read)
            # print()
            if segment_seq not in segm_already_tried and len(segment_seq) > 5:
                # print("testing partial_hit end:", exon_id, e_start, e_stop, s_start, s_stop, final_last_start, segment_seq )
                add_exon_to_mam(read_seq, ref_chr_id, segment_seq, e_start, e_stop, exon_id, mam_instance, min_acc, annot_label = '_partial_segment_end' )
                segm_already_tried.add(segment_seq)


    # finally add eventual partial hits of the flanks if any in the solution But they are required not to overlap any exons 
    segm_already_tried = set()
    for (ref_chr_id, f_start, f_stop) in unique_flank_choordinates_partial_hits:
        ref_chr_id, s_start, s_stop = unique_flank_choordinates_partial_hits[(ref_chr_id, f_start, f_stop)]
        flank_seq = ref_flank_sequences[ref_chr_id][(f_start, f_stop)]
        flank_id = "flank_{0}_{1}".format(f_start, f_stop)

        segment_seq = flank_seq[s_start - f_start:  ]   # segment is MEM coordinated i.e. inclusive, so we subtract one here
        if segment_seq not in segm_already_tried and len(segment_seq) > 5:
            # print("Testing start flank segment:", f_start, s_stop, segment_seq )
            add_exon_to_mam(read_seq, ref_chr_id, segment_seq, f_start, f_stop, flank_id, mam_instance, min_acc, annot_label = '_partial_flank_start')
            segm_already_tried.add(segment_seq)

        segment_seq = flank_seq[: len(flank_seq) - (f_stop - (s_stop + 1)) ]  # segment is MEM coordinated i.e. inclusive, so we subtract one here
        if segment_seq not in segm_already_tried and len(segment_seq) > 5:
            # print("Testing end flank segment:", s_start, f_stop, segment_seq )
            add_exon_to_mam(read_seq, ref_chr_id, segment_seq, f_start, f_stop, flank_id, mam_instance, min_acc, annot_label = '_partial_flank_end')
            segm_already_tried.add(segment_seq)


    mam_instance = list(filter(lambda x: not("_start" in x.exon_id and x.c >= 50) and not("_end" in x.exon_id and x.d <= len(read_seq) - 50), mam_instance))

    ###################################################################################################
    ###################################################################################################
    ###################################################################################################
    # print("MAM INSTANCE", mam_instance)
    if mam_instance:
        mam_solution, value, unique = colinear_solver.read_coverage_mam_score(mam_instance)
    else:
        return [], -1, []
    # print(mam_solution)
    covered = sum([mam.d-mam.c + 1 for mam in mam_solution])
    if len(mam_solution) > 0:
        non_covered_regions = []
        non_covered_regions.append( mam_solution[0].c )
        if len(mam_solution) > 1:
            for mam1, mam2 in zip(mam_solution[:-1],mam_solution[1:]):
                non_covered_regions.append( mam2.c - mam1.d -1 )
            # non_covered_regions = [mam2.c-mam1.d for mam1, mam2 in zip(mam_solution[:-1],mam_solution[1:])]
        # add beginning and end
        non_covered_regions.append( len(read_seq)  - mam_solution[-1].d )


    else:
        non_covered_regions = []
    # print(non_covered_regions)
    return non_covered_regions, value, mam_solution


