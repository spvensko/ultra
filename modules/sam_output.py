import pysam
from itertools import groupby
from operator import itemgetter

def get_segments(read_aln, ref_aln, predicted_exons):
    segments = []
    ref_seq_break_points = set()
    prev = 0
    # print(predicted_exons)
    for p1,p2 in predicted_exons:
        ref_seq_break_points.add( p2 - p1 + prev )
        prev += p2-p1
    
    # print('ref_seq_break_points', ref_seq_break_points)

    curr_ref_pos = 0
    ref_aln_break_points = []
    for i, n in enumerate(ref_aln):
        if curr_ref_pos in ref_seq_break_points:
            ref_aln_break_points.append(i)

        if n != '-':
            curr_ref_pos += 1
    # print(curr_ref_pos)
    if n != '-' and curr_ref_pos in ref_seq_break_points: 
        ref_aln_break_points.append(i)


    # remove any consecutive breakpoints caused by insertions in junctions
    ref_aln_break_points_no_consecutive = []
    for k, g in groupby( enumerate(ref_aln_break_points), key=lambda x: x[0] - x[1]):
        consecutive_group_of_coords = list(map(itemgetter(1), g))
        # print(consecutive_group_of_coords)
        ref_aln_break_points_no_consecutive.append(consecutive_group_of_coords[0])

    # print('ref_aln_break_points', ref_aln_break_points)
    # print('ref_aln_break_points_no_consecutive', ref_aln_break_points_no_consecutive)
    # print(len(ref_aln_break_points_no_consecutive))
    e_start = 0
    for i,e_stop in enumerate(ref_aln_break_points_no_consecutive):
        if i == len(ref_aln_break_points_no_consecutive) - 1:
            segments.append( (read_aln[ e_start : ], ref_aln[ e_start : ]) )
        else:
            segments.append( (read_aln[ e_start : e_stop ], ref_aln[ e_start : e_stop ]) )
        e_start = e_stop
    return segments

def get_type(n1, n2):
    if n1 == n2:
        return '='
    elif n1 == '-':
        return 'D'
    elif n2 == '-':
        return 'I'
    else:
        return 'X'

def get_cigars(segments):
    segments_cigar = []
    first, last = 0, len(segments) - 1
    start_offset = 0
    for i, (read, ref) in enumerate(segments):
        # print()
        cigar_types = []
        cigar_lengths = []
        prev_type = get_type(read[0], ref[0])
        length = 1
        for n1,n2 in zip(read[1:], ref[1:]):
            curr_type = get_type(n1, n2)
            if curr_type == prev_type:
                length += 1
            else:
                cigar_types.append(prev_type)
                cigar_lengths.append(length)
                # cigar_tuples.append((length, prev_type))
                length = 1
                prev_type = curr_type
        
        cigar_types.append(prev_type)
        cigar_lengths.append(length)
        # cigar_tuples.append((length, prev_type))

        if i == first:
            if cigar_types[0] == 'D':
                start_offset = cigar_lengths[0]
                del cigar_lengths[0]
                del cigar_types[0]

            elif cigar_types[0] == 'I':
                cigar_types[0] = "S"
        if i == last:
            if cigar_types[-1] == 'D':
                del cigar_lengths[-1]
                del cigar_types[-1]
            elif cigar_types[-1] == 'I':
                cigar_types[-1] = "S"

        segment_cigar = "".join([str(l)+t for l,t in zip(cigar_lengths,cigar_types) ])
        segments_cigar.append(segment_cigar)

    # print(start_offset, 'segments_cigar', segments_cigar)
    return segments_cigar, start_offset #"".join([str(length)+ type_ for length, type_ in c ])

def get_genomic_cigar(read_aln, ref_aln, predicted_exons):
    # print('here', read_aln)
    # print('here', ref_aln)
    segments = get_segments(read_aln, ref_aln, predicted_exons)
    cigars, start_offset = get_cigars(segments)
    # print('cigar segments', cigars)
    genomic_cigar = []
    intron_lengths = [e2[0] - e1[1] for e1, e2 in zip(predicted_exons[:-1], predicted_exons[1:])]
    for i in range(len(cigars)):
        if i <= len(intron_lengths) -1:
            genomic_cigar.append( cigars[i] + '{0}N'.format( intron_lengths[i] ) )
        else:
            genomic_cigar.append( cigars[i]  )

    genomic_cigar = "".join(s for s in genomic_cigar)
    return genomic_cigar, start_offset



def main(read_id, ref_id, classification, predicted_exons, read_aln, ref_aln, annotated_to_transcript_id, alignment_outfile, is_rc, is_secondary, map_score, aln_score = 0):
    # print(ref_id, classification, predicted_exons, read_aln, ref_aln, alignment_outfile)
    read_sam_entry = pysam.AlignedSegment(alignment_outfile.header)
    if classification != 'unaligned':
        genomic_cigar, start_offset = get_genomic_cigar(read_aln, ref_aln, predicted_exons)
        # if genomic_cigar == "":
        #     print(classification, is_rc, is_secondary, aln_score)
        #     print('genomic cigar:', genomic_cigar, read_id)
        #     print(read_aln)
        #     print(ref_aln)
        #     print(predicted_exons)
        read_sam_entry.cigarstring = genomic_cigar 
        read_sam_entry.reference_start = predicted_exons[0][0] + start_offset
        read_sam_entry.mapping_quality = map_score 

        # print(predicted_exons[0][0], start_offset)

    else:
        read_sam_entry.cigarstring = '*'
        read_sam_entry.reference_start = -1

    read_sam_entry.query_name = read_id

    if is_secondary and is_rc:
        read_sam_entry.flag = 256 + 16 
    elif is_secondary:
        read_sam_entry.flag = 256
    elif is_rc:
        read_sam_entry.flag = 16 
    else:
        read_sam_entry.flag = 0 

    read_sam_entry.reference_name = ref_id
    read_sam_entry.mapping_quality = 60 # TODO: calculate mapping quality 
    # print(annotated_to_transcript_id)
    read_sam_entry.set_tag('AN', annotated_to_transcript_id)
    read_sam_entry.set_tag('CN', classification)

    # read_sam_entry.reference_star = 


    alignment_outfile.write(read_sam_entry)
    # sys.exit()


