import pysam


def get_segments(read_aln, ref_aln, predicted_exons):
    segments = []
    ref_seq_break_points = []
    prev = 0
    for p1,p2 in predicted_exons:
        ref_seq_break_points.append( p2 - p1 + prev )
        prev += p2-p1

    e_start = 0
    for e_stop in ref_seq_break_points:
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
    c = []
    for read, ref in segments:
        prev_type = get_type(read[0], ref[0])
        length = 1
        for n1,n2 in zip(read[1:], ref[1:]):
            curr_type = get_type(n1, n2)
            if curr_type == prev_type:
                length += 1
            else:
                c.append(str(length) + prev_type)
                length = 1
                prev_type = curr_type
        

        c.append(str(length) + prev_type)

    print(c)
    return c #"".join([str(length)+ type_ for length, type_ in c ])

def get_genomic_cigar(read_aln, ref_aln, predicted_exons):

    segments = get_segments(read_aln, ref_aln, predicted_exons)
    cigars = get_cigars(segments)
    genomic_cigar = []
    intron_lengths = [e2[0] - e1[1] for e1, e2 in zip(predicted_exons[:-1], predicted_exons[1:])]
    for i in range(len(cigars)):
        if i <= len(intron_lengths) -1:
            genomic_cigar.append( cigars[i] + '{0}N'.format( intron_lengths[i] ) )
        else:
            genomic_cigar.append( cigars[i]  )

    genomic_cigar = "".join(s for s in genomic_cigar)
    return genomic_cigar



def main(read_id, ref_id, classification, predicted_exons, read_aln, ref_aln, annotated_to_transcript_id, alignment_outfile):
    print(ref_id, classification, predicted_exons, read_aln, ref_aln, alignment_outfile)
    read_sam_entry = pysam.AlignedSegment(alignment_outfile.header)
    
    genomic_cigar = get_genomic_cigar(read_aln, ref_aln, predicted_exons)
    print(genomic_cigar)
    read_sam_entry.query_name = read_id
    read_sam_entry.flag = 0 # TODO: add reverse complements
    read_sam_entry.reference_name = ref_id
    read_sam_entry.reference_start = predicted_exons[0][0]
    read_sam_entry.mapping_quality = 60 # TODO: calculate mapping quality 
    read_sam_entry.cigarstring = genomic_cigar
    print(annotated_to_transcript_id)
    read_sam_entry.set_tag('AN', annotated_to_transcript_id)
    read_sam_entry.set_tag('CN', classification)

    # read_sam_entry.reference_star = 





    alignment_outfile.write(read_sam_entry)
    # sys.exit()